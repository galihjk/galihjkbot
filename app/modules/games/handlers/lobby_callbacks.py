from __future__ import annotations

from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.core.exceptions import (
    InvalidGameStateError,
    PlayerAlreadyJoinedError,
    PlayerLimitReachedError,
    SessionNotFoundError,
)
from app.database.models.user import User
from app.database.repositories.game_repository import find_by_id
from app.filters.group_only import GroupOnly
from app.modules.games.engine.manager import GameManager
from app.modules.games.keyboards.lobby import LobbyCallback
from app.modules.games.router import router


@router.callback_query(GroupOnly(), LobbyCallback.filter())
async def handle_lobby_callback(
    callback: CallbackQuery,
    callback_data: LobbyCallback,
    game_manager: GameManager,
    db_session: AsyncSession,
    current_user: User,
    admin_role: AdminRole | None = None,
) -> None:
    session_id = callback_data.session_id
    action = callback_data.action

    try:
        if action == "join":
            await game_manager.join_game(
                db_session, session_id=session_id, internal_user_id=current_user.id
            )
            await callback.answer("Berhasil gabung!")
        elif action == "leave":
            await game_manager.leave_game(
                db_session, session_id=session_id, internal_user_id=current_user.id
            )
            await callback.answer("Kamu keluar dari lobby.")
        elif action == "extend":
            await game_manager.extend_lobby(
                db_session, session_id=session_id, internal_user_id=current_user.id
            )
            await callback.answer("Waktu lobby diperpanjang jadi 60 detik lagi!")
        elif action == "ready":
            await game_manager.mark_ready(
                db_session, session_id=session_id, internal_user_id=current_user.id
            )
            await callback.answer("Kamu siap!")
        elif action == "cancel":
            await _handle_cancel(callback, game_manager, db_session, current_user, admin_role)
        else:
            await callback.answer()
    except SessionNotFoundError:
        await callback.answer("Sesi game tidak ditemukan.", show_alert=True)
    except InvalidGameStateError:
        await callback.answer(
            "Aksi tidak valid untuk status game saat ini.", show_alert=True
        )
    except PlayerAlreadyJoinedError:
        await callback.answer("Kamu sudah bergabung.", show_alert=True)
    except PlayerLimitReachedError:
        await callback.answer("Lobby penuh.", show_alert=True)


async def _handle_cancel(
    callback: CallbackQuery,
    game_manager: GameManager,
    db_session: AsyncSession,
    current_user: User,
    admin_role: AdminRole | None,
) -> None:
    session_id = LobbyCallback.unpack(callback.data).session_id
    game_session = await find_by_id(db_session, session_id)
    if game_session is None:
        await callback.answer("Sesi game tidak ditemukan.", show_alert=True)
        return

    is_creator = game_session.created_by_user_id == current_user.id
    if not (is_creator or admin_role is not None):
        await callback.answer(
            "Hanya pembuat lobby atau admin yang bisa membatalkan.", show_alert=True
        )
        return

    await game_manager.cancel_game(
        db_session,
        session_id=session_id,
        reason="Dibatalkan oleh pengguna",
        cancelled_by_user_id=current_user.id,
    )
    await callback.answer("Game dibatalkan.")
