from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.core.enums import GameEventType, GamePlayerStatus
from app.database.repositories.game_repository import find_player, log_event
from app.modules.games.callbacks import GameCallback
from app.modules.games.engine.base_game import BaseGame
from app.modules.games.engine.context import GameContext
from app.modules.games.engine.result import GameResult
from app.modules.games.implementations.kursi_kosong import keyboards, state as game_state, texts
from app.modules.games.implementations.kursi_kosong.metadata import (
    KURSI_KOSONG_METADATA,
    ROUND_TIMEOUT_SECONDS,
)
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)


def _save_state(context: GameContext, state: dict) -> None:
    """Simpan state_json dan tandai kolom berubah (lihat game-development-guide.md §5)."""
    context.game_session.state_json = state
    flag_modified(context.game_session, "state_json")


class KursiKosongGame(BaseGame):
    metadata = KURSI_KOSONG_METADATA

    async def initialize(self, context: GameContext) -> None:
        alive_ids = [p.user_id for p in context.active_players]
        _save_state(context, game_state.build_initial_state(alive_ids))
        await context.db_session.flush()

    async def start(self, context: GameContext) -> None:
        await context.bot.send_message(context.telegram_chat_id, texts.WELCOME_TEXT)
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

        seat_number = int(seat_str)
        user_id = self._resolve_user_id(context, callback.from_user.id)
        if user_id is None or user_id not in state["alive_user_ids"]:
            await callback.answer(texts.NOT_IN_GAME_ALERT, show_alert=True)
            return

        existing_seat = game_state.already_seated(state, user_id)
        if existing_seat is not None:
            await callback.answer(
                texts.SEAT_ALREADY_MINE_ALERT.format(seat=existing_seat), show_alert=True
            )
            return

        holder_id = game_state.seat_holder(state, seat_number)
        if holder_id is not None:
            await callback.answer(
                texts.SEAT_TAKEN_ALERT.format(holder=self._display_name(context, holder_id)),
                show_alert=True,
            )
            return

        claimed = game_state.claim_seat(state, seat_number, user_id)
        if not claimed:
            await callback.answer(
                texts.SEAT_TAKEN_ALERT.format(holder="pemain lain"), show_alert=True
            )
            return

        _save_state(context, state)
        await context.db_session.flush()
        await callback.answer(texts.SEAT_CLAIMED_TOAST.format(seat=seat_number))
        await self._refresh_round_message(context, state)

        if game_state.is_round_complete(state):
            context.game_manager.cancel_turn_timeout(context.session_id)
            await self._resolve_round(context)

    async def handle_timeout(self, context: GameContext, timer_key: str) -> None:
        await self._resolve_round(context)

    async def finish(self, context: GameContext, result: GameResult) -> None:
        return  # notifikasi kemenangan sudah dikirim di _resolve_round

    async def _begin_round(self, context: GameContext) -> None:
        state = context.game_session.state_json
        game_state.start_new_round(state)
        _save_state(context, state)
        await context.db_session.flush()

        players = [
            p for p in context.active_players if p.user_id in state["alive_user_ids"]
        ]
        seat_total = game_state.seat_count(state)
        players_by_id = {p.user_id: p.display_name for p in context.active_players}

        text = texts.render_round_start(
            state["round"], players, seat_total, ROUND_TIMEOUT_SECONDS
        )
        keyboard = keyboards.build_seat_keyboard(
            context.session_id, state["round"], seat_total, state["seats"], players_by_id
        )
        message = await context.bot.send_message(
            context.telegram_chat_id, text, reply_markup=keyboard
        )
        state["round_message_id"] = message.message_id
        _save_state(context, state)
        await context.db_session.flush()

        context.game_manager.schedule_turn_timeout(
            context.session_id, ROUND_TIMEOUT_SECONDS
        )

    async def _refresh_round_message(self, context: GameContext, state: dict) -> None:
        message_id = state.get("round_message_id")
        if message_id is None:
            return

        seat_total = game_state.seat_count(state)
        players_by_id = {p.user_id: p.display_name for p in context.active_players}
        keyboard = keyboards.build_seat_keyboard(
            context.session_id, state["round"], seat_total, state["seats"], players_by_id
        )
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=context.telegram_chat_id,
                message_id=message_id,
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception(
                "Gagal memperbarui keyboard kursi, session %s", context.session_id
            )

    async def _resolve_round(self, context: GameContext) -> None:
        state = context.game_session.state_json
        survivors, eliminated_user_id = game_state.resolve_round(state)
        _save_state(context, state)
        await context.db_session.flush()

        players_by_id = {p.user_id: p for p in context.active_players}
        eliminated_name = (
            players_by_id[eliminated_user_id].display_name
            if eliminated_user_id in players_by_id
            else None
        )

        if eliminated_user_id is not None:
            player = await find_player(
                context.db_session, context.session_id, eliminated_user_id
            )
            if player is not None:
                player.status = GamePlayerStatus.ELIMINATED.value
                player.eliminated_at = utcnow()
            await log_event(
                context.db_session,
                context.session_id,
                GameEventType.PLAYER_ACTION.value,
                actor_user_id=eliminated_user_id,
                payload={"action": "eliminated", "round": state["round"]},
            )
            await context.db_session.flush()

        survivor_names = [
            players_by_id[uid].display_name
            for uid in survivors
            if uid in players_by_id
        ]
        await context.bot.send_message(
            context.telegram_chat_id,
            texts.render_round_result(eliminated_name, survivor_names),
        )

        if len(survivors) <= 1:
            winner_id = survivors[0] if survivors else None
            winner_name = (
                players_by_id[winner_id].display_name
                if winner_id in players_by_id
                else "?"
            )
            await context.bot.send_message(
                context.telegram_chat_id, texts.render_winner(winner_name)
            )

            if winner_id is not None:
                player = await find_player(
                    context.db_session, context.session_id, winner_id
                )
                if player is not None:
                    player.status = GamePlayerStatus.WINNER.value
                await context.db_session.flush()

            result = GameResult(
                winner_user_id=winner_id,
                summary=f"{winner_name} menang",
                payload={"rounds": state["round"]},
            )
            await context.game_manager.finish_game(context, result)
        else:
            await self._begin_round(context)

    def _resolve_user_id(self, context: GameContext, telegram_user_id: int) -> int | None:
        for player in context.active_players:
            if player.telegram_user_id == telegram_user_id:
                return player.user_id
        return None

    def _display_name(self, context: GameContext, user_id: int) -> str:
        for player in context.active_players:
            if player.user_id == user_id:
                return player.display_name
        return "?"
