from __future__ import annotations

from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.group_only import GroupOnly
from app.modules.games.callbacks import GameCallback
from app.modules.games.engine.manager import GameManager
from app.modules.games.router import router


@router.callback_query(GroupOnly(), GameCallback.filter())
async def handle_game_callback(
    callback: CallbackQuery,
    callback_data: GameCallback,
    game_manager: GameManager,
    db_session: AsyncSession,
) -> None:
    await game_manager.handle_callback(
        db_session, session_id=callback_data.session_id, callback=callback
    )
