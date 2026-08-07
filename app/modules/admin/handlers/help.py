from __future__ import annotations

from aiogram.filters import Command
from aiogram.types import Message

from app.core.enums import AdminRole
from app.filters.admin import IsAdmin
from app.filters.private_only import PrivateOnly
from app.modules.admin.presenters import format_admin_help
from app.modules.admin.router import router


@router.message(PrivateOnly(), IsAdmin(), Command("adminhelp"))
async def handle_admin_help(
    message: Message, admin_role: AdminRole | None = None
) -> None:
    await message.answer(format_admin_help(admin_role))
