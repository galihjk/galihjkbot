from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Any

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.orm.attributes import flag_modified

from app.core.enums import GameEventType, GamePlayerStatus
from app.database.repositories.game_repository import find_all_players, find_player, log_event
from app.database.repositories.user_repository import find_by_id as find_user_by_id
from app.modules.games.callbacks import GameCallback
from app.modules.games.engine.base_game import BaseGame
from app.modules.games.engine.context import GameContext
from app.modules.games.engine.result import GameResult
from app.modules.games.engine.score import ScoreBreakdown
from app.modules.games.implementations.kursi_kosong import (
    keyboards,
    scoring,
    state as game_state,
    texts,
)
from app.modules.games.implementations.kursi_kosong.metadata import (
    CONTEST_WINDOW_SECONDS,
    KURSI_KOSONG_METADATA,
    MESSAGE_PAUSE_SECONDS,
    MIN_ACTION_WINDOW_SECONDS,
    ROUND_TIMEOUT_SECONDS,
    SEAT_REVEAL_MAX_SECONDS,
    SEAT_REVEAL_MIN_SECONDS,
)
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)


def _save_state(context: GameContext, state: dict) -> None:
    """Simpan state_json dan tandai kolom berubah (lihat game-development-guide.md §5)."""
    context.game_session.state_json = state
    flag_modified(context.game_session, "state_json")


# CATATAN: method di bawah pakai `context.db_session.commit()`, BUKAN cuma
# `.flush()`, di setiap titik mutasi -- ronde Kursi Kosong berisi banyak
# `asyncio.sleep()` (pacing) dan panggilan Telegram (bisa lambat/timeout
# nyata, lihat development-history.md) di ANTARA mutasi-mutasi itu. Kalau
# transaksi dibiarkan terbuka sepanjang itu, koneksi SQLite lain (mis. update
# `users.last_seen_at` dari pesan pengguna LAIN yang lewat di waktu yang
# sama) bisa gagal dengan "database is locked" begitu busy_timeout terlewati.
# `expire_on_commit=False` di session_factory bikin commit di tengah jalan
# ini aman -- objek ORM tetap valid & bisa terus dimutasi sesudahnya.


_EDIT_RETRY_DELAYS = (0, 0.5, 1.5)


async def _call_with_retry(coro_factory, *, max_attempts: int = 3):
    """Jalankan `coro_factory()` (callable TANPA argumen, mengembalikan
    coroutine BARU tiap dipanggil supaya bisa diulang) -- otomatis tunggu &
    ulangi kalau kena flood control Telegram (`TelegramRetryAfter`, sudah
    menyebutkan `retry_after` yang pasti dari Telegram sendiri, jadi memang
    layak ditunggu & dicoba lagi, beda dari error jaringan acak). Bug nyata
    yang memicu ini: pesan awal ronde baru (`_begin_round`) kena flood
    control lalu TIDAK ADA yang menangkap -- ronde gagal mulai SELAMANYA,
    lihat development-history.md. Exception lain dibiarkan menjalar apa
    adanya (bukan kondisi yang bisa diperbaiki dengan menunggu)."""
    for attempt in range(max_attempts):
        try:
            return await coro_factory()
        except TelegramRetryAfter as exc:
            if attempt == max_attempts - 1:
                raise
            logger.warning(
                "Flood control Telegram, tunggu %s detik (percobaan %s/%s)",
                exc.retry_after, attempt + 1, max_attempts,
            )
            await asyncio.sleep(exc.retry_after + 0.5)


async def _edit_round_message_with_fallback(
    context: GameContext, state: dict, text: str, reply_markup
) -> None:
    """Edit pesan ronde di tempat (desain §36-37): 3x percobaan (langsung,
    +500ms, +1.500ms), tiap percobaan tetap tahan flood control lewat
    `_call_with_retry`. Kalau ke-3 nya tetap gagal (bukan flood control --
    itu sudah ditangani terpisah di tiap percobaan), keyboard yang basi
    SELAMANYA lebih berbahaya daripada mengirim pesan baru: kirim pesan baru
    berisi teks+keyboard yang sama, jadikan itu pesan ronde yang otoritatif
    (`round_message_id` baru), naikkan `message_version` (bookkeeping/audit,
    lihat `handle_callback` untuk penegakan penolakan pesan lama)."""
    message_id = state.get("round_message_id")
    last_exc: Exception | None = None
    for delay in _EDIT_RETRY_DELAYS:
        if delay:
            await asyncio.sleep(delay)
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_text(
                    text,
                    chat_id=context.telegram_chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup,
                )
            )
            return
        except Exception as exc:  # noqa: BLE001 -- sengaja tangkap luas, lihat docstring
            last_exc = exc

    logger.warning(
        "Edit pesan ronde gagal %s kali (session %s), kirim pesan baru sebagai "
        "gantinya: %s",
        len(_EDIT_RETRY_DELAYS), context.session_id, last_exc,
    )
    new_message = await _call_with_retry(
        lambda: context.bot.send_message(
            context.telegram_chat_id, text, reply_markup=reply_markup
        )
    )
    state["round_message_id"] = new_message.message_id
    state["message_version"] = state.get("message_version", 1) + 1
    _save_state(context, state)
    await context.db_session.commit()


class KursiKosongGame(BaseGame):
    metadata = KURSI_KOSONG_METADATA

    async def initialize(self, context: GameContext) -> None:
        alive_ids = [p.user_id for p in context.active_players]
        _save_state(context, game_state.build_initial_state(alive_ids))
        await context.db_session.commit()

    async def start(self, context: GameContext) -> None:
        await _call_with_retry(
            lambda: context.bot.send_message(context.telegram_chat_id, texts.WELCOME_TEXT)
        )
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS+1)
        await self._begin_round(context)

    async def handle_message(self, context: GameContext, message: Any) -> None:
        return  # tidak butuh input pesan, hanya tombol

    async def handle_callback(self, context: GameContext, callback: Any) -> None:
        parsed = GameCallback.unpack(callback.data)
        # separator "-" (bukan ":") karena CallbackData.pack() aiogram sendiri
        # memakai ":" untuk memisahkan field, jadi ":" tidak bisa dipakai di
        # dalam nilai `data`.
        round_str, seat_str = parsed.data.split("-", 1)

        state = context.game_session.state_json

        # Wajib divalidasi dari awal (bukan bug simple_game, lihat
        # game-development-guide.md §6): callback dari ronde lama ditolak.
        if int(round_str) != state["round"]:
            await callback.answer(texts.STALE_ROUND_ALERT, show_alert=True)
            return

        # Desain §36: kalau edit pesan ronde gagal berulang, bot terpaksa
        # kirim pesan BARU sebagai pengganti (lihat `_edit_round_message_with_fallback`)
        # -- pesan LAMA (nomor ronde-nya kebetulan masih sama, jadi tidak
        # tertangkap validasi di atas) tidak lagi otoritatif, tombolnya harus
        # ditolak supaya cuma ada satu sumber tombol yang valid per ronde.
        current_message_id = state.get("round_message_id")
        callback_message_id = getattr(getattr(callback, "message", None), "message_id", None)
        if current_message_id is not None and callback_message_id != current_message_id:
            await callback.answer(texts.STALE_ROUND_ALERT, show_alert=True)
            return

        seat_number = int(seat_str)
        user_id = context.acting_user_id
        if user_id is None or user_id not in state["alive_user_ids"]:
            await callback.answer(texts.NOT_IN_GAME_ALERT, show_alert=True)
            return

        existing_seat = game_state.already_seated(state, user_id)
        if existing_seat is not None:
            await callback.answer(
                texts.SEAT_ALREADY_MINE_ALERT.format(seat=existing_seat), show_alert=True
            )
            return

        # §10 desain: klik apa pun dari pemain yang belum punya kursi dihitung
        # aksi valid untuk anti-AFK, apa pun hasilnya setelah titik ini
        # (kursi kosong, kursi terisi, atau ditolak karena masih terikat
        # kontes lain) -- ditandai & disimpan sekali di sini, bukan di tiap
        # cabang (termasuk cabang yang return lebih awal di bawah).
        game_state.mark_action_taken(state, user_id)
        _save_state(context, state)
        await context.db_session.commit()

        # Satu pemain hanya boleh terikat ke satu kontes aktif dalam satu
        # waktu -- klik ke kursi lain saat masih menunggu hasil kursi
        # sebelumnya ditolak (bukan pindah otomatis), sesuai keputusan user.
        active_contest_seat = game_state.user_active_contest_seat(state, user_id)
        if active_contest_seat is not None and active_contest_seat != seat_number:
            await callback.answer(
                texts.ALREADY_CONTESTING_ALERT.format(seat=active_contest_seat),
                show_alert=True,
            )
            return

        holder_id = game_state.seat_holder(state, seat_number)
        if holder_id is not None:
            await callback.answer(
                random.choice(texts.SEAT_TAKEN_ALERTS).format(
                    holder=self._display_name(context, holder_id)
                ),
                show_alert=True,
            )
            return

        joined, is_new = game_state.join_contest(state, seat_number, user_id)
        if not joined:
            # Klik dobel ke kontes yang sama -- tidak ada perubahan state,
            # cukup jawab toast lagi.
            await callback.answer(texts.CONTESTING_TOAST.format(seat=seat_number))
            return

        _save_state(context, state)
        await context.db_session.commit()

        if is_new:
            context.game_manager.schedule_timer(
                context.session_id, f"contest:{seat_number}", CONTEST_WINDOW_SECONDS
            )

        await callback.answer(texts.CONTESTING_TOAST.format(seat=seat_number))
        await self._refresh_round_message(context, state)

    async def handle_timeout(self, context: GameContext, timer_key: str) -> None:
        # timer_key berbentuk "turn:{session_id}:round" atau
        # "turn:{session_id}:contest:{seat_number}" (lihat schedule_timer di
        # game-development-guide.md §7).
        parts = timer_key.split(":")
        if parts[-1] == "round":
            state = context.game_session.state_json
            # Kontes yang masih menunggu (jendelanya belum habis) dipaksa
            # selesai dulu supaya tidak ada kursi yang "menggantung" saat
            # ronde ditutup -- timernya sendiri juga dibatalkan supaya tidak
            # nembak lagi setelah state ronde berikutnya direset.
            for seat_number in [int(n) for n in list(state["contests"])]:
                context.game_manager.cancel_timer(
                    context.session_id, f"contest:{seat_number}"
                )
                await self._settle_contest(context, seat_number)
            await self._resolve_round(context)
        elif parts[-2] == "contest":
            seat_number = int(parts[-1])
            await self._resolve_contest(context, seat_number)
        elif parts[-2] == "countdown":
            seconds_left = int(parts[-1])
            await self._send_countdown_reminder(context, seconds_left)

    async def finish(self, context: GameContext, result: GameResult) -> None:
        return  # notifikasi kemenangan sudah dikirim di _resolve_round

    async def calculate_scores(
        self, context: GameContext, result: GameResult
    ) -> dict[int, ScoreBreakdown]:
        outcomes = await self._build_score_outcomes(context)
        results = scoring.compute_scores(outcomes)
        return {uid: res.breakdown for uid, res in results.items()}

    async def _build_score_outcomes(self, context: GameContext) -> list[scoring.PlayerOutcome]:
        state = context.game_session.state_json
        initial_player_count = state.get(
            "initial_player_count", len(context.active_players)
        )
        final_round = state["round"]
        all_players = await find_all_players(context.db_session, context.session_id)
        outcomes = []
        for player in all_players:
            if player.status not in (
                GamePlayerStatus.WINNER.value,
                GamePlayerStatus.ELIMINATED.value,
                GamePlayerStatus.AFK.value,
            ):
                continue
            outcomes.append(
                scoring.PlayerOutcome(
                    user_id=player.user_id,
                    status=player.status,
                    eliminated_round=player.eliminated_round,
                    final_round=final_round,
                    initial_player_count=initial_player_count,
                )
            )
        return outcomes

    async def _send_final_results(self, context: GameContext) -> None:
        outcomes = await self._build_score_outcomes(context)
        results = scoring.compute_scores(outcomes)
        names_by_id: dict[int, str] = {}
        for uid in results:
            user = await find_user_by_id(context.db_session, uid)
            names_by_id[uid] = (
                user.display_name or user.first_name or "?" if user is not None else "?"
            )
        try:
            await _call_with_retry(
                lambda: context.bot.send_message(
                    context.telegram_chat_id, texts.render_final_results(results, names_by_id)
                )
            )
        except Exception:
            logger.exception(
                "Gagal mengirim hasil akhir & skor, session %s", context.session_id
            )

    async def _begin_round(self, context: GameContext) -> None:
        state = context.game_session.state_json
        game_state.start_new_round(state)
        _save_state(context, state)
        await context.db_session.commit()

        players = [
            p for p in context.active_players if p.user_id in state["alive_user_ids"]
        ]
        seat_total = game_state.seat_count(state)
        # §25 desain: tinggal 2 pemain/1 kursi -- ronde final, pakai flourish
        # pembuka khusus alih-alih header ronde biasa.
        is_final = len(state["alive_user_ids"]) == 2

        waiting_text = texts.render_round_waiting(
            state["round"], players, seat_total, is_final=is_final
        )
        # Titik yang pernah bikin game macet SELAMANYA (lihat development-history.md):
        # kalau ini gagal tanpa retry, ronde ini tidak punya pesan sama sekali
        # untuk dipasangi keyboard -- tidak ada yang bisa "diselamatkan" lagi.
        # `_call_with_retry` menangani flood control (kasus nyata yang terjadi)
        # dengan menunggu & mencoba lagi; kegagalan LAIN (bukan flood control)
        # tetap dibiarkan menjalar apa adanya -- gunakan /cancelgame kalau
        # sampai terjadi supaya grup tidak terkunci menunggu game yang macet.
        message = await _call_with_retry(
            lambda: context.bot.send_message(context.telegram_chat_id, waiting_text)
        )
        state["round_message_id"] = message.message_id
        _save_state(context, state)
        await context.db_session.commit()

        # Kursi sengaja tidak langsung muncul bareng teks ronde -- beri jeda
        # acak dulu (kesan "musik akan segera dimulai"), baru teks DAN
        # keyboard sama-sama diganti lewat edit. Timer 15 detik dihitung
        # SETELAH kursi muncul, bukan dari saat teks ronde dikirim.
        await asyncio.sleep(random.uniform(SEAT_REVEAL_MIN_SECONDS, SEAT_REVEAL_MAX_SECONDS))

        ready_text = self._render_ready_text(context, state)
        keyboard = self._build_round_keyboard(context, state)
        await _edit_round_message_with_fallback(context, state, ready_text, keyboard)

        # Titik ini = kursi/keyboard BENAR sudah bisa diklik -- dipakai
        # sebagai acuan "jendela keadilan" (MIN_ACTION_WINDOW_SECONDS) di
        # _resolve_round supaya pemain yang belum sempat beraksi tidak
        # salah dicap AFK kalau ronde ditutup jauh lebih cepat dari wajar.
        state["ready_at"] = utcnow().isoformat()
        _save_state(context, state)
        await context.db_session.commit()

        context.game_manager.schedule_turn_timeout(
            context.session_id, ROUND_TIMEOUT_SECONDS
        )
        # Reminder countdown 5/3 detik (§24 desain) -- cuma dijadwalkan kalau
        # ronde memang cukup panjang untuk menyisakan waktu itu (jaga-jaga
        # kalau suatu saat ROUND_TIMEOUT_SECONDS dikonfigurasi lebih pendek).
        if ROUND_TIMEOUT_SECONDS > 5:
            context.game_manager.schedule_timer(
                context.session_id, "countdown:5", ROUND_TIMEOUT_SECONDS - 5
            )
        if ROUND_TIMEOUT_SECONDS > 3:
            context.game_manager.schedule_timer(
                context.session_id, "countdown:3", ROUND_TIMEOUT_SECONDS - 3
            )

    def _render_ready_text(
        self, context: GameContext, state: dict, extra_note: str | None = None
    ) -> str:
        players = [
            p for p in context.active_players if p.user_id in state["alive_user_ids"]
        ]
        seat_total = game_state.seat_count(state)
        is_final = len(state["alive_user_ids"]) == 2
        return texts.render_round_ready(
            state["round"],
            players,
            seat_total,
            ROUND_TIMEOUT_SECONDS,
            is_final=is_final,
            extra_note=extra_note,
        )

    def _build_round_keyboard(
        self, context: GameContext, state: dict
    ) -> InlineKeyboardMarkup:
        seat_total = game_state.seat_count(state)
        players_by_id = {p.user_id: p.display_name for p in context.active_players}
        return keyboards.build_seat_keyboard(
            context.session_id,
            state["round"],
            seat_total,
            state["seats"],
            players_by_id,
            state["contests"],
        )

    async def _refresh_round_message(self, context: GameContext, state: dict) -> None:
        if state.get("round_message_id") is None:
            return

        text = self._render_ready_text(context, state)
        keyboard = self._build_round_keyboard(context, state)
        await _edit_round_message_with_fallback(context, state, text, keyboard)

    async def _send_countdown_reminder(self, context: GameContext, seconds_left: int) -> None:
        """Edit pesan ronde menjadi mengandung reminder countdown 5/3 detik
        (§24 desain) -- keyboard & sisa isi teks tetap mencerminkan state
        kursi/kontes TERKINI (bisa saja sudah berubah sejak ronde dimulai)."""
        state = context.game_session.state_json
        if state.get("round_message_id") is None:
            return

        text = self._render_ready_text(
            context, state, extra_note=texts.COUNTDOWN_NOTES.get(seconds_left)
        )
        keyboard = self._build_round_keyboard(context, state)
        await _edit_round_message_with_fallback(context, state, text, keyboard)

    async def _resolve_contest(self, context: GameContext, seat_number: int) -> None:
        """Dipanggil saat timer jendela kontes (1,2 detik) sebuah kursi
        habis secara normal (bukan dipaksa oleh timeout ronde)."""
        state = context.game_session.state_json
        settled = await self._settle_contest(context, seat_number)
        if not settled:
            return  # sudah diresolve jalur lain (mis. dipaksa timeout ronde)

        if game_state.is_round_complete(state):
            context.game_manager.cancel_turn_timeout(context.session_id)
            # Reminder countdown belum tentu sudah nembak (ronde selesai
            # lebih cepat dari 15 detik) -- batalkan supaya tidak menyusul
            # muncul di pesan ronde BERIKUTNYA (pola sama seperti kontes
            # dibatalkan dari timeout ronde, guide §7).
            context.game_manager.cancel_timer(context.session_id, "countdown:5")
            context.game_manager.cancel_timer(context.session_id, "countdown:3")
            await self._resolve_round(context)

    async def _settle_contest(self, context: GameContext, seat_number: int) -> bool:
        """Inti penyelesaian kontes satu kursi: tentukan pemenang (atau
        langsung tetapkan kalau cuma 1 kontestan), simpan state, kirim
        narasi kalau relevan. Dipakai baik oleh `_resolve_contest` (jalur
        normal) maupun dipaksa dari `handle_timeout` saat ronde berakhir
        lebih dulu. Return False kalau kontes sudah tidak ada (dobel proses)."""
        state = context.game_session.state_json
        contest = game_state.pop_contest(state, seat_number)
        if contest is None:
            return False

        contestants = contest["contestants"]
        winner_id = (
            contestants[0]
            if len(contestants) == 1
            else game_state.pick_contest_winner(contestants)
        )
        game_state.claim_seat(state, seat_number, winner_id)
        _save_state(context, state)
        await context.db_session.commit()

        if len(contestants) >= 2:
            players_by_id = {p.user_id: p.display_name for p in context.active_players}
            winner_name = players_by_id.get(winner_id, "?")
            contestant_names = [players_by_id.get(uid, "?") for uid in contestants]
            loser_names = [
                players_by_id.get(uid, "?") for uid in contestants if uid != winner_id
            ]
            try:
                await _call_with_retry(
                    lambda: context.bot.send_message(
                        context.telegram_chat_id,
                        texts.render_contest_result(
                            seat_number, contestant_names, winner_name, loser_names
                        ),
                    )
                )
            except Exception:
                logger.exception(
                    "Gagal mengirim narasi kontes kursi %s, session %s",
                    seat_number, context.session_id,
                )
            await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

        await self._refresh_round_message(context, state)
        return True

    async def _close_round_message(self, context: GameContext, state: dict) -> None:
        """Tutup pesan ronde yang baru selesai: ganti jadi snapshot kursi
        final (tanpa tombol), lalu beri jeda supaya terasa "waktu habis"
        sebelum narasi hasil ronde dikirim di pesan terpisah."""
        message_id = state.get("round_message_id")
        if message_id is None:
            return

        seat_total = game_state.seat_count(state)
        players_by_id = {p.user_id: p.display_name for p in context.active_players}
        closed_text = texts.render_round_closed(
            state["round"], seat_total, state["seats"], players_by_id
        )
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_text(
                    closed_text,
                    chat_id=context.telegram_chat_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
                )
            )
        except Exception:
            logger.exception(
                "Gagal menutup pesan ronde, session %s", context.session_id
            )
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

    async def _resolve_round(self, context: GameContext) -> None:
        state = context.game_session.state_json

        await self._close_round_message(context, state)

        survivors, eliminated_ids = game_state.resolve_round(state)
        _save_state(context, state)
        await context.db_session.commit()

        # Jendela keadilan (MIN_ACTION_WINDOW_SECONDS): kalau ronde ini
        # selesai jauh lebih cepat dari wajar (kursi terakhir keburu penuh
        # dalam hitungan detik), pemain yang belum sempat beraksi diberi
        # keuntungan diragukan -- dicap ELIMINATED (kalah wajar), bukan AFK.
        # Konsekuensi yang disadari: AFK sungguhan cuma terdeteksi akurat
        # kalau rondenya berjalan cukup lama.
        ready_at = state.get("ready_at")
        fair_window_passed = True
        if ready_at is not None:
            elapsed = (utcnow() - datetime.fromisoformat(ready_at)).total_seconds()
            fair_window_passed = elapsed >= MIN_ACTION_WINDOW_SECONDS

        players_by_id = {p.user_id: p for p in context.active_players}
        normal_names: list[str] = []
        afk_names: list[str] = []
        for uid in eliminated_ids:
            is_afk = fair_window_passed and not game_state.took_action(state, uid)
            player = await find_player(context.db_session, context.session_id, uid)
            if player is not None:
                player.status = (
                    GamePlayerStatus.AFK.value
                    if is_afk
                    else GamePlayerStatus.ELIMINATED.value
                )
                player.eliminated_at = utcnow()
                player.eliminated_round = state["round"]
            await log_event(
                context.db_session,
                context.session_id,
                GameEventType.PLAYER_ACTION.value,
                actor_user_id=uid,
                payload={
                    "action": "afk" if is_afk else "eliminated",
                    "round": state["round"],
                },
            )
            name = players_by_id[uid].display_name if uid in players_by_id else "?"
            (afk_names if is_afk else normal_names).append(name)
        await context.db_session.commit()

        survivor_names = [
            players_by_id[uid].display_name
            for uid in survivors
            if uid in players_by_id
        ]
        try:
            await _call_with_retry(
                lambda: context.bot.send_message(
                    context.telegram_chat_id,
                    texts.render_round_result(normal_names, afk_names, survivor_names),
                )
            )
        except Exception:
            logger.exception(
                "Gagal mengirim narasi hasil ronde, session %s", context.session_id
            )
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

        if not survivors:
            # Kasus ekstrem: tidak ada satu kursi pun diklaim ronde ini --
            # semua pemain hidup tereliminasi bersamaan. MC umumkan tidak
            # ada pemenang (bukan jalur error/gagal §39 desain).
            #
            # Kirim narasi dulu (dibungkus try/except, sama seperti panggilan
            # Telegram lain di sini) -- kegagalan MENGIRIM PESAN tidak boleh
            # sampai membatalkan `finish_game()` di bawah, karena itu yang
            # mengubah status jadi FINISHED, commit skor, dan mengirim
            # "Mau main lagi?" (lihat development-history.md: pernah ada
            # TelegramNetworkError di sini yang bikin finish_game TIDAK
            # PERNAH terpanggil).
            try:
                await _call_with_retry(
                    lambda: context.bot.send_message(
                        context.telegram_chat_id, texts.render_no_winner()
                    )
                )
            except Exception:
                logger.exception(
                    "Gagal mengirim pesan tanpa pemenang, session %s", context.session_id
                )
            await asyncio.sleep(MESSAGE_PAUSE_SECONDS)
            await self._send_final_results(context)

            result = GameResult(
                winner_user_id=None,
                summary="Tidak ada pemenang",
                payload={"rounds": state["round"]},
            )
            await context.game_manager.finish_game(context, result)
        elif len(survivors) == 1:
            winner_id = survivors[0]
            winner_name = (
                players_by_id[winner_id].display_name
                if winner_id in players_by_id
                else "?"
            )
            try:
                await _call_with_retry(
                    lambda: context.bot.send_message(
                        context.telegram_chat_id, texts.render_winner(winner_name)
                    )
                )
            except Exception:
                logger.exception(
                    "Gagal mengirim pesan pemenang, session %s", context.session_id
                )

            player = await find_player(context.db_session, context.session_id, winner_id)
            if player is not None:
                player.status = GamePlayerStatus.WINNER.value
            await context.db_session.commit()

            await asyncio.sleep(MESSAGE_PAUSE_SECONDS)
            await self._send_final_results(context)

            result = GameResult(
                winner_user_id=winner_id,
                summary=f"{winner_name} menang",
                payload={"rounds": state["round"]},
            )
            await context.game_manager.finish_game(context, result)
        else:
            await self._begin_round(context)

    def _display_name(self, context: GameContext, user_id: int) -> str:
        for player in context.active_players:
            if player.user_id == user_id:
                return player.display_name
        return "?"
