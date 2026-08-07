from __future__ import annotations

from aiogram import F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserStatus
from app.database.repositories.user_repository import (
    count_groups_for_user,
    find_by_id,
    find_by_telegram_id,
    find_by_username,
    find_users_page,
    parse_user_code,
)
from app.filters.admin import IsAdmin
from app.filters.private_only import PrivateOnly
from app.modules.admin.callbacks import AdminCallback
from app.modules.admin.keyboards import build_back_to_dashboard_keyboard
from app.modules.admin.presenters import format_user_detail, format_user_list
from app.modules.admin.router import router
from app.utils.pagination import DEFAULT_PAGE_SIZE, clamp_page
from app.utils.text import parse_list_command_args

_VALID_STATUSES = {status.value for status in UserStatus}


@router.message(PrivateOnly(), IsAdmin(), Command("users"))
async def handle_users(
    message: Message,
    db_session: AsyncSession,
    command: CommandObject,
) -> None:
    status, requested_page = parse_list_command_args(
        command.args or "", _VALID_STATUSES
    )

    page = await find_users_page(
        db_session, page=requested_page, page_size=DEFAULT_PAGE_SIZE, status=status
    )
    if requested_page > page.total_pages:
        page = await find_users_page(
            db_session,
            page=clamp_page(requested_page, page.total_pages),
            page_size=DEFAULT_PAGE_SIZE,
            status=status,
        )

    await message.answer(format_user_list(page))


@router.message(PrivateOnly(), IsAdmin(), Command("user"))
async def handle_user_detail(
    message: Message,
    db_session: AsyncSession,
    command: CommandObject,
) -> None:
    identifier = (command.args or "").strip()
    if not identifier:
        await message.answer("Gunakan: /user [telegram_id|@username|U-000001]")
        return

    internal_id = parse_user_code(identifier)
    if internal_id is not None:
        user = await find_by_id(db_session, internal_id)
    elif identifier.startswith("@"):
        user = await find_by_username(db_session, identifier)
    elif identifier.isdigit():
        user = await find_by_telegram_id(db_session, int(identifier))
    else:
        user = await find_by_username(db_session, identifier)

    if user is None:
        await message.answer("Pengguna tidak ditemukan.")
        return

    group_count = await count_groups_for_user(db_session, user.id)
    await message.answer(format_user_detail(user, group_count))


@router.callback_query(
    PrivateOnly(), IsAdmin(), AdminCallback.filter(F.action == "users")
)
async def handle_users_callback(
    callback: CallbackQuery,
    db_session: AsyncSession,
) -> None:
    page = await find_users_page(
        db_session, page=1, page_size=DEFAULT_PAGE_SIZE, status=None
    )
    await callback.message.edit_text(
        format_user_list(page), reply_markup=build_back_to_dashboard_keyboard()
    )
    await callback.answer()
