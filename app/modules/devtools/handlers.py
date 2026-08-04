from __future__ import annotations

from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.database.models.user import User
from app.database.repositories.user_repository import get_or_create_virtual_player
from app.filters.group_only import GroupOnly
from app.middlewares.persona import PersonaMiddleware
from app.modules.devtools.router import router

MAX_PERSONA = 7


@router.message(
    GroupOnly(), Command(*(f"p{i}" for i in range(MAX_PERSONA + 1)))
)
async def handle_persona_switch(
    message: Message,
    command: CommandObject,
    real_user: User | None,
    real_admin_role: AdminRole | None,
    persona_middleware: PersonaMiddleware,
    db_session: AsyncSession,
) -> None:
    if real_user is None or real_admin_role is None:
        return  # bukan admin -> command dianggap tidak ada (silent)

    index = int(command.command[1:])
    chat_id = message.chat.id

    if index == 0:
        persona_middleware.clear(chat_id, real_user.telegram_user_id)
        name = real_user.display_name or real_user.first_name or "dirimu sendiri"
        await message.answer(f"Kembali sebagai {name}.")
        return

    virtual_user = await get_or_create_virtual_player(db_session, index)
    persona_middleware.set_persona(chat_id, real_user.telegram_user_id, index)
    await message.answer(f"Sekarang kamu berperan sebagai {virtual_user.display_name}.")
