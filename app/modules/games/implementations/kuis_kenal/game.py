from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.orm.attributes import flag_modified

from app.core.enums import GamePlayerStatus, GameStatus
from app.database.repositories.game_repository import find_by_id as find_session_by_id
from app.database.repositories.game_repository import find_player
from app.database.repositories.user_repository import find_by_id as find_user_by_id
from app.modules.games import private_input
from app.modules.games.callbacks import GameCallback
from app.modules.games.engine.base_game import BaseGame
from app.modules.games.engine.context import GameContext, PlayerInfo
from app.modules.games.engine.result import GameResult
from app.modules.games.engine.score import ScoreBreakdown
from app.modules.games.implementations.kuis_kenal import keyboards, links, questions
from app.modules.games.implementations.kuis_kenal import state as game_state
from app.modules.games.implementations.kuis_kenal import texts
from app.modules.games.implementations.kuis_kenal.metadata import (
    ANSWER_CONTEXT_TTL_SECONDS,
    ANSWER_MAX_LENGTH,
    ANSWER_TIMEOUT_SECONDS,
    EDIT_RETRY_DELAYS,
    JUDGE_CONTEXT_TTL_SECONDS,
    JUDGING_TIMEOUT_SECONDS,
    KUIS_KENAL_METADATA,
    MESSAGE_PAUSE_SECONDS,
    QUESTION_OPTIONS_PER_TURN,
    QUESTION_PICK_CONTEXT_TTL_SECONDS,
    QUESTION_PICK_TIMEOUT_SECONDS,
    QUESTION_REROLL_LIMIT,
    REVEAL_MAX_SECONDS,
    REVEAL_MIN_SECONDS,
)

logger = logging.getLogger(__name__)


def _save_state(game_session: Any, state: dict) -> None:
    game_session.state_json = state
    flag_modified(game_session, "state_json")


# CATATAN: commit (bukan cuma flush) dipanggil di tiap titik mutasi -- ada
# banyak asyncio.sleep()/panggilan Telegram di antara mutasi-mutasi di modul
# ini, dan membiarkan transaksi terbuka sepanjang itu bisa memicu "database
# is locked" di koneksi lain (lihat development-history.md soal Kursi
# Kosong, masalah yang sama berpotensi terjadi di game manapun yang punya
# pacing serupa).


async def _call_with_retry(coro_factory, *, max_attempts: int = 3):
    """Otomatis tunggu & ulangi kalau kena flood control Telegram
    (`TelegramRetryAfter`, sudah menyebutkan `retry_after` pasti dari
    Telegram). Exception lain dibiarkan menjalar apa adanya."""
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


async def _edit_or_send_new(context: GameContext, chat_id: int, message_id: int | None, text: str, reply_markup=None) -> int:
    """Coba edit pesan yang sudah ada (retry 3x, jeda [0, 0.5, 1.5] detik --
    §15 desain). Kalau tetap gagal (atau belum ada pesan sama sekali), kirim
    pesan baru. Return message_id OTORITATIF setelahnya."""
    if message_id is not None:
        for delay in EDIT_RETRY_DELAYS:
            if delay:
                await asyncio.sleep(delay)
            try:
                await _call_with_retry(
                    lambda: context.bot.edit_message_text(
                        text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup,
                    )
                )
                return message_id
            except Exception:  # noqa: BLE001 -- sengaja luas, lihat docstring
                continue
        logger.warning(
            "Edit pesan gagal %s kali (chat %s), kirim pesan baru sebagai gantinya",
            len(EDIT_RETRY_DELAYS), chat_id,
        )

    new_message = await _call_with_retry(
        lambda: context.bot.send_message(chat_id, text, reply_markup=reply_markup)
    )
    return new_message.message_id


def _is_authoritative(state: dict, pointer_key: str, callback: Any) -> bool:
    current = state.get(pointer_key)
    callback_message_id = getattr(getattr(callback, "message", None), "message_id", None)
    return current is None or callback_message_id == current


async def _fetch_player_info(db_session: Any, user_id: int) -> PlayerInfo:
    user = await find_user_by_id(db_session, user_id)
    if user is None:
        return PlayerInfo(user_id=user_id, telegram_user_id=0, display_name="?")
    return PlayerInfo(
        user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        display_name=user.display_name or user.first_name or "Pemain",
    )


_bot_username_cache: dict[int, str] = {}


async def _get_bot_username(bot: Any) -> str:
    bot_id = getattr(bot, "id", 0)
    cached = _bot_username_cache.get(bot_id)
    if cached is not None:
        return cached
    me = await bot.get_me()
    _bot_username_cache[bot_id] = me.username
    return me.username


class KuisKenalGame(BaseGame):
    metadata = KUIS_KENAL_METADATA

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self, context: GameContext) -> None:
        user_ids = [p.user_id for p in context.active_players]
        state = game_state.build_initial_state(user_ids)
        _save_state(context.game_session, state)
        await context.db_session.commit()

    async def start(self, context: GameContext) -> None:
        await _call_with_retry(
            lambda: context.bot.send_message(context.telegram_chat_id, texts.WELCOME_TEXT)
        )
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)
        await self._begin_turn(context)

    async def finish(self, context: GameContext, result: GameResult) -> None:
        return  # notifikasi kemenangan sudah dikirim di _finish_game

    # ------------------------------------------------------------------
    # Giliran
    # ------------------------------------------------------------------

    async def _begin_turn(self, context: GameContext) -> None:
        state = context.game_session.state_json
        game_state.begin_turn(state)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        subject = self._player(context, state["current_subject_id"])
        total_turns = len(state["all_user_ids"])
        text = texts.render_turn_start(subject, state["round"], total_turns)
        message = await _call_with_retry(
            lambda: context.bot.send_message(context.telegram_chat_id, text)
        )
        state["public_message_id"] = message.message_id
        _save_state(context.game_session, state)
        await context.db_session.commit()

        await self._open_question_selection(context, state)

    async def _open_question_selection(self, context: GameContext, state: dict) -> None:
        question_ids = questions.draw_question_options(
            used_question_ids=state["used_question_ids"], count=QUESTION_OPTIONS_PER_TURN,
        )
        game_state.offer_questions(state, question_ids)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        await asyncio.sleep(random.uniform(REVEAL_MIN_SECONDS, REVEAL_MAX_SECONDS))

        bot_username = await _get_bot_username(context.bot)
        keyboard = keyboards.build_group_choose_question_link(
            bot_username, context.session_id, state["round"], state["question_nonce"]
        )
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_reply_markup(
                    chat_id=context.telegram_chat_id,
                    message_id=state["public_message_id"],
                    reply_markup=keyboard,
                )
            )
        except Exception:
            logger.exception(
                "Gagal menampilkan tombol pilih soal, session %s", context.session_id
            )

        context.game_manager.schedule_turn_timeout(context.session_id, QUESTION_PICK_TIMEOUT_SECONDS)

    def _player(self, context: GameContext, user_id: int | None) -> PlayerInfo:
        for player in context.active_players:
            if player.user_id == user_id:
                return player
        return PlayerInfo(user_id=user_id or 0, telegram_user_id=0, display_name="?")

    async def _strip_public_keyboard(self, context: GameContext, state: dict) -> None:
        message_id = state.get("public_message_id")
        if message_id is None:
            return
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_reply_markup(
                    chat_id=context.telegram_chat_id,
                    message_id=message_id,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
                )
            )
        except Exception:
            logger.exception("Gagal melepas keyboard pesan grup, session %s", context.session_id)

    # ------------------------------------------------------------------
    # Deep link (/start kk-*)
    # ------------------------------------------------------------------

    async def handle_deep_link(
        self,
        payload: str,
        *,
        message: Any,
        db_session: Any,
        acting_user_id: int,
        game_manager: Any,
    ) -> None:
        parsed = links.parse_deep_link_payload(payload)
        if parsed is None:
            return

        async with game_manager.lock_session(parsed.session_id):
            game_session = await find_session_by_id(db_session, parsed.session_id)
            if (
                game_session is None
                or game_session.status != GameStatus.RUNNING.value
                or game_session.game_key != self.metadata.key
            ):
                await message.answer(texts.INVALID_LINK_ALERT)
                return

            state = game_session.state_json
            if state["round"] != parsed.round_number:
                await message.answer(texts.INVALID_LINK_ALERT)
                return
            if not game_state.is_participant(state, acting_user_id):
                await message.answer(texts.NOT_A_PARTICIPANT_ALERT)
                return

            if parsed.purpose == "question_select":
                await self._activate_question_select(
                    message, db_session, game_session, state, acting_user_id, parsed
                )
            elif parsed.purpose == "answer":
                await self._activate_answer(
                    message, db_session, game_session, state, acting_user_id, parsed
                )
            elif parsed.purpose == "judge":
                await self._activate_judge(
                    message, db_session, game_session, state, acting_user_id, parsed
                )

    async def _activate_question_select(
        self, message: Any, db_session: Any, game_session: Any, state: dict, user_id: int, parsed
    ) -> None:
        if (
            not game_state.is_current_subject(state, user_id)
            or parsed.nonce != state.get("question_nonce")
            or state["phase"] != game_state.Phase.QUESTION_SELECT.value
        ):
            await message.answer(texts.INVALID_LINK_ALERT)
            return

        private_input.register_private_input(
            user_id=user_id, session_id=game_session.id, purpose="question_select",
            round_number=state["round"], nonce=parsed.nonce, ttl_seconds=QUESTION_PICK_CONTEXT_TTL_SECONDS,
        )

        question_texts = [
            texts.format_question_text(questions.get_question(qid).text, "kamu")
            for qid in state["offered_question_ids"]
        ]
        text = texts.render_question_options(question_texts)
        keyboard = keyboards.build_private_question_keyboard(
            game_session.id, state["round"], state["message_version"],
            len(state["offered_question_ids"]),
            can_reroll=state["question_reroll_count"] < QUESTION_REROLL_LIMIT,
        )
        sent = await _call_with_retry(lambda: message.answer(text, reply_markup=keyboard))
        state["subject_private_message_id"] = sent.message_id
        _save_state(game_session, state)
        await db_session.commit()

    async def _activate_answer(
        self, message: Any, db_session: Any, game_session: Any, state: dict, user_id: int, parsed
    ) -> None:
        if (
            game_state.is_current_subject(state, user_id)
            or parsed.nonce != state.get("answer_nonce")
            or state["phase"] != game_state.Phase.ANSWERING.value
        ):
            await message.answer(texts.INVALID_LINK_ALERT)
            return
        if game_state.has_confirmed_answer(state, user_id):
            await message.answer(texts.ALREADY_CONFIRMED_ALERT)
            return

        private_input.register_private_input(
            user_id=user_id, session_id=game_session.id, purpose="answer",
            round_number=state["round"], nonce=parsed.nonce, ttl_seconds=ANSWER_CONTEXT_TTL_SECONDS,
        )

        subject = await _fetch_player_info(db_session, state["current_subject_id"])
        question = questions.get_question(state["selected_question_id"])
        question_text = texts.format_question_text(question.text, subject.display_name)
        text = texts.render_private_answer_prompt(question_text, subject)
        await _call_with_retry(lambda: message.answer(text))

    async def _activate_judge(
        self, message: Any, db_session: Any, game_session: Any, state: dict, user_id: int, parsed
    ) -> None:
        if (
            not game_state.is_current_subject(state, user_id)
            or parsed.nonce != state.get("judge_nonce")
            or state["phase"] != game_state.Phase.JUDGING.value
        ):
            await message.answer(texts.INVALID_LINK_ALERT)
            return

        private_input.register_private_input(
            user_id=user_id, session_id=game_session.id, purpose="judge",
            round_number=state["round"], nonce=parsed.nonce, ttl_seconds=JUDGE_CONTEXT_TTL_SECONDS,
        )

        question = questions.get_question(state["selected_question_id"])
        question_text = texts.format_question_text(question.text, "kamu")
        intro = texts.render_judging_intro(question_text)
        body = texts.render_judging(state["answer_groups"])
        keyboard = keyboards.build_judging_keyboard(
            game_session.id, state["round"], state["message_version"], state["answer_groups"]
        )
        sent = await _call_with_retry(
            lambda: message.answer(f"{intro}\n\n{body}", reply_markup=keyboard)
        )
        state["judging_message_id"] = sent.message_id
        _save_state(game_session, state)
        await db_session.commit()

    # ------------------------------------------------------------------
    # Callback dalam-game
    # ------------------------------------------------------------------

    async def handle_callback(self, context: GameContext, callback: Any) -> None:
        parsed = GameCallback.unpack(callback.data)
        try:
            round_str, version_str, action, value_str = parsed.data.split("-", 3)
            round_number = int(round_str)
            version = int(version_str)
        except ValueError:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        state = context.game_session.state_json
        if round_number != state["round"]:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        user_id = context.acting_user_id
        if user_id is None or not game_state.is_participant(state, user_id):
            await callback.answer(texts.NOT_IN_GAME_ALERT, show_alert=True)
            return

        handlers = {
            "qp": self._handle_question_pick,
            "qr": self._handle_question_reroll,
            "ac": self._handle_answer_confirm,
            "ae": self._handle_answer_change,
            "jt": self._handle_judgement_toggle,
            "jd": self._handle_judgement_done,
        }
        handler = handlers.get(action)
        if handler is None:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        await handler(context, state, callback, version, value_str, user_id)

    async def _handle_question_pick(
        self, context: GameContext, state: dict, callback: Any, version: int, value_str: str, user_id: int
    ) -> None:
        if not game_state.is_current_subject(state, user_id):
            await callback.answer(texts.NOT_YOUR_TURN_TO_PICK_ALERT, show_alert=True)
            return
        if state["phase"] != game_state.Phase.QUESTION_SELECT.value:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if version != state["message_version"]:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if not _is_authoritative(state, "subject_private_message_id", callback):
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        try:
            index = int(value_str)
            question_id = state["offered_question_ids"][index]
        except (ValueError, IndexError):
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        game_state.select_question(state, question_id)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        await callback.answer(texts.render_question_selected_ack())
        await self._close_private_message(context, callback, texts.render_question_selected_ack())
        await self._publish_question(context, state)

    async def _handle_question_reroll(
        self, context: GameContext, state: dict, callback: Any, version: int, value_str: str, user_id: int
    ) -> None:
        if not game_state.is_current_subject(state, user_id):
            await callback.answer(texts.NOT_YOUR_TURN_TO_PICK_ALERT, show_alert=True)
            return
        if state["phase"] != game_state.Phase.QUESTION_SELECT.value:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if version != state["message_version"]:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if not _is_authoritative(state, "subject_private_message_id", callback):
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if state["question_reroll_count"] >= QUESTION_REROLL_LIMIT:
            await callback.answer(texts.REROLL_LIMIT_REACHED_ALERT, show_alert=True)
            return

        new_ids = questions.draw_question_options(
            used_question_ids=state["used_question_ids"], count=QUESTION_OPTIONS_PER_TURN,
        )
        game_state.reroll_questions(state, new_ids, reroll_limit=QUESTION_REROLL_LIMIT)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        question_texts = [
            texts.format_question_text(questions.get_question(qid).text, "kamu")
            for qid in state["offered_question_ids"]
        ]
        text = texts.render_question_options(question_texts)
        keyboard = keyboards.build_private_question_keyboard(
            context.session_id, state["round"], state["message_version"],
            len(state["offered_question_ids"]),
            can_reroll=state["question_reroll_count"] < QUESTION_REROLL_LIMIT,
        )
        chat_id = callback.message.chat.id
        new_id = await _edit_or_send_new(context, chat_id, state.get("subject_private_message_id"), text, keyboard)
        state["subject_private_message_id"] = new_id
        _save_state(context.game_session, state)
        await context.db_session.commit()

        await callback.answer("🔀 Soal baru sudah ditampilkan.")

    async def _publish_question(self, context: GameContext, state: dict) -> None:
        subject = self._player(context, state["current_subject_id"])
        question = questions.get_question(state["selected_question_id"])
        question_text = texts.format_question_text(question.text, subject.display_name)
        text = texts.render_public_question(question_text, subject)

        bot_username = await _get_bot_username(context.bot)
        keyboard = keyboards.build_group_answer_link(
            bot_username, context.session_id, state["round"], state["answer_nonce"]
        )

        new_id = await _edit_or_send_new(
            context, context.telegram_chat_id, state.get("public_message_id"), text, keyboard
        )
        state["public_message_id"] = new_id
        _save_state(context.game_session, state)
        await context.db_session.commit()

        context.game_manager.schedule_turn_timeout(context.session_id, ANSWER_TIMEOUT_SECONDS)

    async def _close_private_message(self, context: GameContext, callback: Any, final_text: str) -> None:
        chat = getattr(getattr(callback, "message", None), "chat", None)
        message_id = getattr(getattr(callback, "message", None), "message_id", None)
        if chat is None or message_id is None:
            return
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_text(final_text, chat_id=chat.id, message_id=message_id)
            )
        except Exception:
            logger.exception("Gagal menutup pesan privat, session %s", context.session_id)

    # ------------------------------------------------------------------
    # Jawaban privat & konfirmasi
    # ------------------------------------------------------------------

    async def handle_message(self, context: GameContext, message: Any) -> None:
        state = context.game_session.state_json
        user_id = context.acting_user_id
        pending = private_input.get_private_input(user_id) if user_id is not None else None
        if pending is None or pending.session_id != context.session_id:
            return

        if pending.purpose in ("question_select", "judge"):
            await message.answer(texts.render_no_active_private_prompt_hint())
            return
        if pending.purpose != "answer":
            return

        if (
            pending.round_number != state["round"]
            or pending.nonce != state.get("answer_nonce")
            or state["phase"] != game_state.Phase.ANSWERING.value
        ):
            await message.answer(texts.render_no_active_private_prompt_hint())
            private_input.clear_private_input(user_id)
            return
        if not game_state.is_participant(state, user_id) or game_state.is_current_subject(state, user_id):
            return
        if game_state.has_confirmed_answer(state, user_id):
            await message.answer(texts.ALREADY_CONFIRMED_ALERT)
            return

        text = message.text
        if text is None:
            await message.answer(texts.ANSWER_MUST_BE_TEXT_ALERT)
            return
        if text.startswith("/"):
            await message.answer(texts.ANSWER_CANNOT_BE_COMMAND_ALERT)
            return
        stripped = text.strip()
        if not stripped:
            await message.answer(texts.ANSWER_EMPTY_ALERT)
            return
        if len(stripped) > ANSWER_MAX_LENGTH:
            await message.answer(texts.ANSWER_TOO_LONG_ALERT)
            return

        game_state.store_answer_draft(state, user_id, stripped)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        keyboard = keyboards.build_answer_confirmation_keyboard(
            context.session_id, state["round"], state["message_version"]
        )
        confirm_text = texts.render_answer_confirmation(stripped)
        existing_pointer = state["answer_confirmation_message_ids"].get(str(user_id))
        chat_id = message.chat.id
        if existing_pointer is not None:
            new_id = await _edit_or_send_new(context, chat_id, existing_pointer, confirm_text, keyboard)
        else:
            sent = await _call_with_retry(lambda: message.answer(confirm_text, reply_markup=keyboard))
            new_id = sent.message_id
        state["answer_confirmation_message_ids"][str(user_id)] = new_id
        _save_state(context.game_session, state)
        await context.db_session.commit()

    async def _handle_answer_confirm(
        self, context: GameContext, state: dict, callback: Any, version: int, value_str: str, user_id: int
    ) -> None:
        if game_state.is_current_subject(state, user_id):
            await callback.answer(texts.SUBJECT_CANNOT_ANSWER_OWN_TURN_ALERT, show_alert=True)
            return
        if state["phase"] != game_state.Phase.ANSWERING.value:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        pointer = state["answer_confirmation_message_ids"].get(str(user_id))
        callback_message_id = getattr(getattr(callback, "message", None), "message_id", None)
        if pointer is not None and callback_message_id != pointer:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if game_state.has_confirmed_answer(state, user_id):
            await callback.answer(texts.ALREADY_CONFIRMED_ALERT, show_alert=True)
            return
        draft = game_state.get_answer_draft(state, user_id)
        if draft is None:
            await callback.answer(texts.NO_DRAFT_TO_CONFIRM_ALERT, show_alert=True)
            return

        game_state.confirm_answer(state, user_id)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        chat_id = callback.message.chat.id
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_text(
                    texts.render_answer_recorded(), chat_id=chat_id, message_id=pointer
                )
            )
        except Exception:
            logger.exception("Gagal menutup pesan konfirmasi, session %s", context.session_id)
        await callback.answer("✅ Jawaban dikonfirmasi.")

        private_input.clear_private_input(user_id)

        if game_state.all_expected_answers_confirmed(state):
            context.game_manager.cancel_turn_timeout(context.session_id)
            await self._finalize_answering(context, state)

    async def _handle_answer_change(
        self, context: GameContext, state: dict, callback: Any, version: int, value_str: str, user_id: int
    ) -> None:
        if game_state.is_current_subject(state, user_id):
            await callback.answer(texts.SUBJECT_CANNOT_ANSWER_OWN_TURN_ALERT, show_alert=True)
            return
        if state["phase"] != game_state.Phase.ANSWERING.value:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        pointer = state["answer_confirmation_message_ids"].get(str(user_id))
        callback_message_id = getattr(getattr(callback, "message", None), "message_id", None)
        if pointer is not None and callback_message_id != pointer:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if game_state.has_confirmed_answer(state, user_id):
            await callback.answer(texts.ALREADY_CONFIRMED_ALERT, show_alert=True)
            return

        private_input.register_private_input(
            user_id=user_id, session_id=context.session_id, purpose="answer",
            round_number=state["round"], nonce=state["answer_nonce"], ttl_seconds=ANSWER_CONTEXT_TTL_SECONDS,
        )

        chat_id = callback.message.chat.id
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_text(
                    texts.render_answer_change_prompt(), chat_id=chat_id, message_id=pointer
                )
            )
        except Exception:
            logger.exception("Gagal membuka ulang input jawaban, session %s", context.session_id)
        await callback.answer()

    async def _finalize_answering(self, context: GameContext, state: dict) -> None:
        game_state.finalize_answering(state)
        _save_state(context.game_session, state)
        await context.db_session.commit()
        await self._strip_public_keyboard(context, state)
        await self._begin_judging(context, state)

    # ------------------------------------------------------------------
    # Penilaian
    # ------------------------------------------------------------------

    async def _begin_judging(self, context: GameContext, state: dict) -> None:
        subject = self._player(context, state["current_subject_id"])
        question = questions.get_question(state["selected_question_id"])
        question_text = texts.format_question_text(question.text, "kamu")
        intro = texts.render_judging_intro(question_text)
        body = texts.render_judging(state["answer_groups"])
        keyboard = keyboards.build_judging_keyboard(
            context.session_id, state["round"], state["message_version"], state["answer_groups"]
        )

        try:
            sent = await _call_with_retry(
                lambda: context.bot.send_message(
                    subject.telegram_user_id, f"{intro}\n\n{body}", reply_markup=keyboard
                )
            )
        except Exception:
            logger.exception(
                "Gagal mengirim pesan penilaian privat, session %s", context.session_id
            )
            # Subjek tidak bisa dihubungi privat -- giliran tidak bisa dinilai,
            # perlakukan seperti judge timeout (tanpa poin) supaya game tetap lanjut.
            game_state.record_judge_timeout(state)
            _save_state(context.game_session, state)
            await context.db_session.commit()
            await self._advance_or_finish(context, state)
            return

        state["judging_message_id"] = sent.message_id
        _save_state(context.game_session, state)
        await context.db_session.commit()

        try:
            await _call_with_retry(
                lambda: context.bot.send_message(
                    context.telegram_chat_id, texts.render_judging_started_public(subject)
                )
            )
        except Exception:
            logger.exception("Gagal mengirim pesan status penilaian, session %s", context.session_id)

        context.game_manager.schedule_turn_timeout(context.session_id, JUDGING_TIMEOUT_SECONDS)

    async def _handle_judgement_toggle(
        self, context: GameContext, state: dict, callback: Any, version: int, value_str: str, user_id: int
    ) -> None:
        if not game_state.is_current_subject(state, user_id):
            await callback.answer(texts.ONLY_SUBJECT_CAN_JUDGE_ALERT, show_alert=True)
            return
        if state["phase"] != game_state.Phase.JUDGING.value:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if not _is_authoritative(state, "judging_message_id", callback):
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        try:
            group_id = int(value_str)
            game_state.toggle_answer_group(state, group_id)
        except ValueError:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        _save_state(context.game_session, state)
        await context.db_session.commit()

        keyboard = keyboards.build_judging_keyboard(
            context.session_id, state["round"], state["message_version"], state["answer_groups"]
        )
        chat_id = callback.message.chat.id
        message_id = state.get("judging_message_id")
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=keyboard
                )
            )
        except Exception:
            logger.exception("Gagal memperbarui keyboard penilaian, session %s", context.session_id)
        await callback.answer()

    async def _handle_judgement_done(
        self, context: GameContext, state: dict, callback: Any, version: int, value_str: str, user_id: int
    ) -> None:
        if not game_state.is_current_subject(state, user_id):
            await callback.answer(texts.ONLY_SUBJECT_CAN_JUDGE_ALERT, show_alert=True)
            return
        if state["phase"] != game_state.Phase.JUDGING.value:
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return
        if not _is_authoritative(state, "judging_message_id", callback):
            await callback.answer(texts.render_stale_interaction(), show_alert=True)
            return

        context.game_manager.cancel_turn_timeout(context.session_id)
        private_input.clear_private_input(user_id)

        chat_id = callback.message.chat.id
        message_id = state.get("judging_message_id")
        try:
            await _call_with_retry(
                lambda: context.bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
                )
            )
        except Exception:
            logger.exception("Gagal menutup pesan penilaian, session %s", context.session_id)
        await callback.answer("✅ Penilaian selesai.")

        summary = game_state.resolve_turn(state)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        await self._send_turn_result(context, state, summary)
        await self._advance_or_finish(context, state)

    # ------------------------------------------------------------------
    # Timeout
    # ------------------------------------------------------------------

    async def handle_timeout(self, context: GameContext, timer_key: str) -> None:
        if not timer_key.endswith(":round"):
            return

        state = context.game_session.state_json
        phase = state["phase"]
        if phase == game_state.Phase.QUESTION_SELECT.value:
            await self._handle_question_pick_timeout(context, state)
        elif phase == game_state.Phase.ANSWERING.value:
            await self._handle_answer_timeout(context, state)
        elif phase == game_state.Phase.JUDGING.value:
            await self._handle_judge_timeout(context, state)

    async def _handle_question_pick_timeout(self, context: GameContext, state: dict) -> None:
        subject = self._player(context, state["current_subject_id"])
        game_state.record_subject_pick_timeout(state)
        _save_state(context.game_session, state)
        await context.db_session.commit()
        private_input.clear_session_private_inputs(context.session_id)

        await self._strip_public_keyboard(context, state)
        try:
            await _call_with_retry(
                lambda: context.bot.send_message(
                    context.telegram_chat_id, texts.render_timeout("question_pick", subject)
                )
            )
        except Exception:
            logger.exception("Gagal mengirim narasi timeout pilih soal, session %s", context.session_id)
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

        await self._advance_or_finish(context, state)

    async def _handle_answer_timeout(self, context: GameContext, state: dict) -> None:
        confirmed = len(state["final_answers"])
        total = len(game_state.expected_answerer_ids(state))
        if confirmed < total:
            try:
                await _call_with_retry(
                    lambda: context.bot.send_message(
                        context.telegram_chat_id,
                        texts.render_waiting_for_players(confirmed, total)
                        + "\n\nWaktu jawab habis, lanjut dengan jawaban yang sudah masuk.",
                    )
                )
            except Exception:
                logger.exception("Gagal mengirim narasi timeout menjawab, session %s", context.session_id)
            await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

        await self._strip_public_keyboard(context, state)
        await self._finalize_answering(context, state)

    async def _handle_judge_timeout(self, context: GameContext, state: dict) -> None:
        subject = self._player(context, state["current_subject_id"])
        game_state.record_judge_timeout(state)
        _save_state(context.game_session, state)
        await context.db_session.commit()
        private_input.clear_session_private_inputs(context.session_id)

        try:
            await _call_with_retry(
                lambda: context.bot.send_message(
                    context.telegram_chat_id, texts.render_timeout("judge", subject)
                )
            )
        except Exception:
            logger.exception("Gagal mengirim narasi timeout menilai, session %s", context.session_id)
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

        await self._advance_or_finish(context, state)

    # ------------------------------------------------------------------
    # Hasil giliran & akhir game
    # ------------------------------------------------------------------

    def _build_rankings(self, context: GameContext, state: dict) -> list[tuple[PlayerInfo, int]]:
        pairs = [
            (self._player(context, uid), state["scores"].get(str(uid), 0))
            for uid in state["all_user_ids"]
        ]
        pairs.sort(key=lambda pair: pair[1], reverse=True)
        return pairs

    async def _send_turn_result(self, context: GameContext, state: dict, summary: dict) -> None:
        question = questions.get_question(summary["question_id"])
        subject = self._player(context, summary["subject_id"])
        question_text = texts.format_question_text(question.text, subject.display_name)

        successful = [(self._player(context, uid), answer) for uid, answer in summary["successful"]]
        failed = [(self._player(context, uid), answer) for uid, answer in summary["failed"]]

        result_text = texts.render_turn_result(question_text, successful, failed)
        try:
            await _call_with_retry(lambda: context.bot.send_message(context.telegram_chat_id, result_text))
        except Exception:
            logger.exception("Gagal mengirim hasil giliran, session %s", context.session_id)
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

        rankings = self._build_rankings(context, state)
        scoreboard_text = texts.render_scoreboard(rankings)
        try:
            await _call_with_retry(lambda: context.bot.send_message(context.telegram_chat_id, scoreboard_text))
        except Exception:
            logger.exception("Gagal mengirim skor sementara, session %s", context.session_id)
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

    async def _advance_or_finish(self, context: GameContext, state: dict) -> None:
        private_input.clear_session_private_inputs(context.session_id)
        game_state.advance_turn(state)
        _save_state(context.game_session, state)
        await context.db_session.commit()

        if game_state.is_game_complete(state):
            await self._finish_game(context, state)
        else:
            await asyncio.sleep(MESSAGE_PAUSE_SECONDS)
            await self._begin_turn(context)

    async def _finish_game(self, context: GameContext, state: dict) -> None:
        payload = game_state.build_result_payload(state)
        rankings = self._build_rankings(context, state)
        winner_ids = payload["winner_user_ids"]

        final_text = texts.render_final_result(rankings, winner_ids)
        try:
            await _call_with_retry(lambda: context.bot.send_message(context.telegram_chat_id, final_text))
        except Exception:
            logger.exception("Gagal mengirim hasil akhir, session %s", context.session_id)
        await asyncio.sleep(MESSAGE_PAUSE_SECONDS)

        winner_user_id = winner_ids[0] if len(winner_ids) == 1 else None
        if winner_user_id is not None:
            winner_name = self._player(context, winner_user_id).display_name
            score = state["scores"].get(str(winner_user_id), 0)
            summary_text = f"{winner_name} menang dengan {score} jawaban benar."
        else:
            summary_text = "Permainan berakhir seri."

        result = GameResult(winner_user_id=winner_user_id, summary=summary_text, payload=payload)
        await context.game_manager.finish_game(context, result)

    # ------------------------------------------------------------------
    # Skor leaderboard bulanan (§18)
    # ------------------------------------------------------------------

    async def calculate_scores(
        self, context: GameContext, result: GameResult
    ) -> dict[int, ScoreBreakdown]:
        state = context.game_session.state_json
        afk_flags = game_state.calculate_afk_flags(state)
        scores: dict[int, ScoreBreakdown] = {}

        for uid in state["all_user_ids"]:
            activity = state["activity"].get(str(uid), {})
            is_afk = afk_flags.get(uid, False)

            raw_survival = (
                36 * activity.get("answers_confirmed", 0)
                + 44 * activity.get("subject_turns_completed", 0)
            )
            raw_result = 36 * activity.get("correct_answers", 0)

            if is_afk:
                participation = 0
                survival = raw_survival // 2
                result_score = raw_result // 2
            else:
                participation = 10 if activity.get("valid_actions", 0) > 0 else 0
                survival = raw_survival
                result_score = raw_result

            final_score = participation + survival + result_score
            scores[uid] = ScoreBreakdown(
                result_score=result_score,
                participation_score=participation,
                survival_score=survival,
                final_score=final_score,
            )

            player = await find_player(context.db_session, context.session_id, uid)
            if player is not None:
                if is_afk:
                    player.status = GamePlayerStatus.AFK.value
                elif uid == result.winner_user_id:
                    player.status = GamePlayerStatus.WINNER.value
                else:
                    player.status = GamePlayerStatus.ACTIVE.value

        await context.db_session.commit()
        return scores
