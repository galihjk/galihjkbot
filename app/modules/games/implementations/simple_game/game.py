from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.core.enums import GameEventType, GamePlayerStatus
from app.database.repositories.game_repository import find_player, log_event
from app.modules.games.callbacks import GameCallback
from app.modules.games.engine.base_game import BaseGame
from app.modules.games.engine.context import GameContext
from app.modules.games.engine.result import GameResult
from app.modules.games.implementations.simple_game import state as game_state
from app.modules.games.implementations.simple_game import texts
from app.modules.games.implementations.simple_game.keyboards import build_seat_keyboard
from app.modules.games.implementations.simple_game.metadata import (
    ROUND_TIMEOUT_SECONDS,
    SIMPLE_GAME_METADATA,
)
from app.utils.datetime import utcnow


def _save_state(context: GameContext, state: dict) -> None:
    """Simpan state_json dan tandai kolom berubah.

    SQLAlchemy tidak mendeteksi mutasi dict di tempat (in-place) pada kolom
    JSON biasa, jadi flag_modified wajib dipanggil setiap kali `state`
    diubah, walau objeknya sama seperti yang sudah tersimpan sebelumnya.
    """
    context.game_session.state_json = state
    flag_modified(context.game_session, "state_json")


class SimpleGame(BaseGame):
    metadata = SIMPLE_GAME_METADATA

    async def initialize(self, context: GameContext) -> None:
        alive_ids = [p.user_id for p in context.active_players]
        _save_state(context, game_state.build_initial_state(alive_ids))
        await context.db_session.flush()

    async def start(self, context: GameContext) -> None:
        await self._begin_round(context)

    async def handle_message(self, context: GameContext, message: Any) -> None:
        return  # game ini tidak butuh input pesan, hanya tombol

    async def handle_callback(self, context: GameContext, callback: Any) -> None:
        parsed = GameCallback.unpack(callback.data)
        seat_number = int(parsed.data)

        state = context.game_session.state_json
        user_id = self._resolve_user_id(context, callback.from_user.id)

        if user_id is None or user_id not in state["alive_user_ids"]:
            await callback.answer("Kamu tidak dalam permainan ini.", show_alert=True)
            return

        claimed = game_state.claim_seat(state, seat_number, user_id)
        _save_state(context, state)
        await context.db_session.flush()

        if not claimed:
            await callback.answer(
                "Kursi sudah diambil / kamu sudah pilih kursi lain.", show_alert=True
            )
            return

        await callback.answer("Kursi diamankan!")

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

        text = texts.render_round_start(
            state["round"], players, seat_total, ROUND_TIMEOUT_SECONDS
        )
        keyboard = build_seat_keyboard(
            context.session_id, game_state.available_seats(state)
        )
        await context.bot.send_message(
            context.telegram_chat_id, text, reply_markup=keyboard
        )

        context.game_manager.schedule_turn_timeout(
            context.session_id, ROUND_TIMEOUT_SECONDS
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
