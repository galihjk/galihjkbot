from __future__ import annotations

from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.modules.common.router import router
from app.modules.common.texts import HELP_MESSAGE, START_MESSAGE
from app.modules.games.deep_link import try_handle_game_deep_link
from app.modules.games.engine.manager import GameManager
from app.modules.games.engine.registry import GameRegistry


@router.message(CommandStart())
async def handle_start(
    message: Message,
    command: CommandObject,
    db_session: AsyncSession,
    current_user: User,
    game_registry: GameRegistry,
    game_manager: GameManager,
) -> None:
    handled = await try_handle_game_deep_link(
        message,
        command,
        db_session=db_session,
        current_user=current_user,
        game_registry=game_registry,
        game_manager=game_manager,
    )
    if handled:
        return

    name = message.from_user.first_name if message.from_user else "Kawan"
    await message.answer(START_MESSAGE.format(name=name))


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP_MESSAGE)
