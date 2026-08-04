from __future__ import annotations

from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.modules.common.router import router
from app.modules.common.texts import HELP_MESSAGE, START_MESSAGE


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "Kawan"
    await message.answer(START_MESSAGE.format(name=name))


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP_MESSAGE)
