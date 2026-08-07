from __future__ import annotations

from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.modules.games.callbacks import GameCallback
from app.modules.games.engine.manager import GameManager
from app.modules.games.router import router


@router.callback_query(GameCallback.filter())
async def handle_game_callback(
    callback: CallbackQuery,
    callback_data: GameCallback,
    game_manager: GameManager,
    db_session: AsyncSession,
    current_user: User,
) -> None:
    await game_manager.handle_callback(
        db_session,
        session_id=callback_data.session_id,
        callback=callback,
        acting_user_id=current_user.id,
    )
