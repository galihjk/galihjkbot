from __future__ import annotations

from aiogram import F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GroupStatus
from app.database.repositories.group_repository import (
    count_members,
    find_by_telegram_chat_id,
    find_groups_page,
)
from app.filters.admin import IsAdmin
from app.filters.private_only import PrivateOnly
from app.modules.admin.callbacks import AdminCallback
from app.modules.admin.keyboards import build_back_to_dashboard_keyboard
from app.modules.admin.presenters import format_group_detail, format_group_list
from app.modules.admin.router import router
from app.utils.pagination import DEFAULT_PAGE_SIZE, clamp_page
from app.utils.text import parse_list_command_args

_VALID_STATUSES = {status.value for status in GroupStatus}


@router.message(PrivateOnly(), IsAdmin(), Command("groups"))
async def handle_groups(
    message: Message,
    db_session: AsyncSession,
    command: CommandObject,
) -> None:
    status, requested_page = parse_list_command_args(
        command.args or "", _VALID_STATUSES
    )

    page = await find_groups_page(
        db_session, page=requested_page, page_size=DEFAULT_PAGE_SIZE, status=status
    )
    if requested_page > page.total_pages:
        page = await find_groups_page(
            db_session,
            page=clamp_page(requested_page, page.total_pages),
            page_size=DEFAULT_PAGE_SIZE,
            status=status,
        )

    await message.answer(format_group_list(page))


@router.message(PrivateOnly(), IsAdmin(), Command("group"))
async def handle_group_detail(
    message: Message,
    db_session: AsyncSession,
    command: CommandObject,
) -> None:
    identifier = (command.args or "").strip()
    if not identifier or not identifier.lstrip("-").isdigit():
        await message.answer("Gunakan: /group [chat_id]")
        return

    group = await find_by_telegram_chat_id(db_session, int(identifier))
    if group is None:
        await message.answer("Grup tidak ditemukan.")
        return

    member_count = await count_members(db_session, group.id)
    await message.answer(format_group_detail(group, member_count))


@router.callback_query(
    PrivateOnly(), IsAdmin(), AdminCallback.filter(F.action == "groups")
)
async def handle_groups_callback(
    callback: CallbackQuery,
    db_session: AsyncSession,
) -> None:
    page = await find_groups_page(
        db_session, page=1, page_size=DEFAULT_PAGE_SIZE, status=None
    )
    await callback.message.edit_text(
        format_group_list(page), reply_markup=build_back_to_dashboard_keyboard()
    )
    await callback.answer()
