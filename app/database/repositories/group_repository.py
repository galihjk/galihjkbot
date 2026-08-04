from __future__ import annotations

from aiogram.types import Chat
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.group import Group
from app.database.models.group_member import GroupMember
from app.database.models.user import User
from app.utils.datetime import utcnow
from app.utils.pagination import Page


async def upsert_group(session: AsyncSession, chat: Chat) -> Group:
    result = await session.execute(
        select(Group).where(Group.telegram_chat_id == chat.id)
    )
    group = result.scalar_one_or_none()
    now = utcnow()

    if group is None:
        group = Group(
            telegram_chat_id=chat.id,
            title=chat.title,
            username=chat.username,
            chat_type=chat.type,
            bot_joined_at=now,
            last_activity_at=now,
        )
        session.add(group)
    else:
        group.title = chat.title
        group.username = chat.username
        group.chat_type = chat.type
        group.last_activity_at = now

    await session.flush()
    return group


async def upsert_group_member(
    session: AsyncSession, group: Group, user: User
) -> GroupMember:
    result = await session.execute(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    now = utcnow()

    if member is None:
        member = GroupMember(
            group_id=group.id,
            user_id=user.id,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(member)
    else:
        member.last_seen_at = now

    await session.flush()
    return member


async def find_by_id(session: AsyncSession, group_id: int) -> Group | None:
    result = await session.execute(select(Group).where(Group.id == group_id))
    return result.scalar_one_or_none()


async def find_by_telegram_chat_id(
    session: AsyncSession, telegram_chat_id: int
) -> Group | None:
    result = await session.execute(
        select(Group).where(Group.telegram_chat_id == telegram_chat_id)
    )
    return result.scalar_one_or_none()


async def count_groups(session: AsyncSession, status: str | None = None) -> int:
    query = select(func.count()).select_from(Group)
    if status is not None:
        query = query.where(Group.status == status)
    result = await session.execute(query)
    return result.scalar_one()


async def find_groups_page(
    session: AsyncSession,
    page: int,
    page_size: int,
    status: str | None = None,
) -> Page[Group]:
    total_items = await count_groups(session, status)

    query = select(Group).order_by(Group.id)
    if status is not None:
        query = query.where(Group.status == status)
    query = query.limit(page_size).offset((page - 1) * page_size)

    result = await session.execute(query)
    items = list(result.scalars().all())

    return Page(items=items, page=page, page_size=page_size, total_items=total_items)


async def count_members(session: AsyncSession, group_id: int) -> int:
    query = (
        select(func.count())
        .select_from(GroupMember)
        .where(GroupMember.group_id == group_id)
    )
    result = await session.execute(query)
    return result.scalar_one()
