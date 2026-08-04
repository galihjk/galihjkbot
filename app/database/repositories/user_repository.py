from __future__ import annotations

import re
from datetime import datetime

from aiogram.types import User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.group_member import GroupMember
from app.database.models.user import User
from app.utils.datetime import utcnow
from app.utils.pagination import Page

USER_CODE_PATTERN = re.compile(r"^U-(\d+)$", re.IGNORECASE)

VIRTUAL_PLAYER_BASE_TELEGRAM_ID = -900000


def _display_name(telegram_user: TelegramUser) -> str:
    parts = [telegram_user.first_name, telegram_user.last_name]
    return " ".join(part for part in parts if part)


async def upsert_user(session: AsyncSession, telegram_user: TelegramUser) -> User:
    result = await session.execute(
        select(User).where(User.telegram_user_id == telegram_user.id)
    )
    user = result.scalar_one_or_none()
    now = utcnow()

    if user is None:
        user = User(
            telegram_user_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            display_name=_display_name(telegram_user),
            language_code=telegram_user.language_code,
            is_bot=telegram_user.is_bot,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(user)
    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name
        user.display_name = _display_name(telegram_user)
        user.language_code = telegram_user.language_code
        user.last_seen_at = now

    await session.flush()
    return user


def parse_user_code(code: str) -> int | None:
    match = USER_CODE_PATTERN.match(code.strip())
    return int(match.group(1)) if match else None


async def find_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def find_by_telegram_id(
    session: AsyncSession, telegram_user_id: int
) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


async def find_by_username(session: AsyncSession, username: str) -> User | None:
    normalized = username.lstrip("@")
    result = await session.execute(
        select(User).where(func.lower(User.username) == normalized.lower())
    )
    return result.scalar_one_or_none()


async def count_users(session: AsyncSession, status: str | None = None) -> int:
    query = select(func.count()).select_from(User)
    if status is not None:
        query = query.where(User.status == status)
    result = await session.execute(query)
    return result.scalar_one()


async def find_users_page(
    session: AsyncSession,
    page: int,
    page_size: int,
    status: str | None = None,
) -> Page[User]:
    total_items = await count_users(session, status)

    query = select(User).order_by(User.id)
    if status is not None:
        query = query.where(User.status == status)
    query = query.limit(page_size).offset((page - 1) * page_size)

    result = await session.execute(query)
    items = list(result.scalars().all())

    return Page(items=items, page=page, page_size=page_size, total_items=total_items)


async def count_active_since(session: AsyncSession, since: datetime) -> int:
    query = (
        select(func.count()).select_from(User).where(User.last_seen_at >= since)
    )
    result = await session.execute(query)
    return result.scalar_one()


async def get_or_create_virtual_player(session: AsyncSession, index: int) -> User:
    """User palsu untuk testing lewat impersonasi admin (lihat PersonaMiddleware).

    Telegram ID negatif tetap supaya tidak pernah bertabrakan dengan ID
    Telegram asli (yang selalu positif).
    """
    telegram_id = VIRTUAL_PLAYER_BASE_TELEGRAM_ID - index
    user = await find_by_telegram_id(session, telegram_id)
    if user is not None:
        return user

    now = utcnow()
    name = f"Virtual Player {index}"
    user = User(
        telegram_user_id=telegram_id,
        first_name=name,
        display_name=name,
        is_bot=False,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(user)
    await session.flush()
    return user


async def count_groups_for_user(session: AsyncSession, user_id: int) -> int:
    query = (
        select(func.count())
        .select_from(GroupMember)
        .where(GroupMember.user_id == user_id)
    )
    result = await session.execute(query)
    return result.scalar_one()
