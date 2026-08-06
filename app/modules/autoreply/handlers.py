from __future__ import annotations

from aiogram import F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.database.models.group import Group
from app.modules.autoreply.router import router
from app.modules.autoreply.service import AutoreplyService


@router.message(F.text)
async def handle_autoreply_message(
    message: Message,
    db_session: AsyncSession,
    autoreply_service: AutoreplyService,
    admin_role: AdminRole | None = None,
    current_group: Group | None = None,
) -> None:
    await autoreply_service.handle_message(
        message, db_session, current_group, admin_role
    )
