from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.database.models.group import Group
from app.database.models.user import User
from app.database.repositories import leaderboard_repository
from app.filters.group_only import GroupOnly
from app.modules.leaderboard import period, presenters
from app.modules.leaderboard.router import router

logger = logging.getLogger(__name__)

_SUBSCRIBED_STATUSES = {
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
}


async def _refresh_subscription(
    bot: Bot, settings: Settings, current_user: User
) -> bool | None:
    """Cek live status subscribe channel leaderboard & update cache di
    `current_user` (mutasi objek ORM -- otomatis commit lewat
    `DatabaseMiddleware`). `None` = channel belum dikonfigurasi, skip notice
    sama sekali. Kalau cek gagal (bot bukan admin, user belum pernah
    interaksi, dll), cache LAMA dipertahankan -- tidak ditimpa begitu saja."""
    channel_id = settings.telegram_leaderboard_channel_id
    if channel_id is None:
        return None
    try:
        member = await bot.get_chat_member(channel_id, current_user.telegram_user_id)
    except Exception:
        logger.warning(
            "Gagal cek status subscribe channel utk user %s, pakai cache lama.",
            current_user.id,
            exc_info=True,
        )
        return current_user.is_leaderboard_channel_subscribed
    is_subscribed = member.status in _SUBSCRIBED_STATUSES
    current_user.is_leaderboard_channel_subscribed = is_subscribed
    return is_subscribed


@router.message(Command("skor"))
async def handle_skor(
    message: Message,
    bot: Bot,
    db_session: AsyncSession,
    current_user: User,
    settings: Settings,
    current_group: Group | None = None,
) -> None:
    start, end, _ = period.current_period_window(settings.timezone)
    global_total = await leaderboard_repository.sum_user_score(
        db_session, current_user.id, start, end
    )
    group_total: int | None = None
    if current_group is not None:
        group_total = await leaderboard_repository.sum_user_score_in_group(
            db_session, current_user.id, current_group.id, start, end
        )
    lines = [
        presenters.format_own_score(
            global_total, group_total, current_group.title if current_group else None
        )
    ]

    is_subscribed = await _refresh_subscription(bot, settings, current_user)
    if is_subscribed is not None:
        lines.append(
            presenters.format_subscription_notice(
                is_subscribed, settings.telegram_leaderboard_channel_link
            )
        )

    await message.answer("\n\n".join(lines))


@router.message(Command("leaderboard"))
async def handle_leaderboard(
    message: Message, db_session: AsyncSession, settings: Settings
) -> None:
    start, end, _ = period.current_period_window(settings.timezone)
    rows = await leaderboard_repository.sum_global_scores_by_user_subscribed(
        db_session, start, end
    )
    for chunk in presenters.format_global_leaderboard(rows):
        await message.answer(chunk)


@router.message(GroupOnly(), Command("leaderboardgrup"))
async def handle_leaderboard_grup(
    message: Message,
    db_session: AsyncSession,
    settings: Settings,
    current_group: Group,
) -> None:
    start, end, _ = period.current_period_window(settings.timezone)
    rows = await leaderboard_repository.sum_group_scores_by_user(
        db_session, current_group.id, start, end
    )
    for chunk in presenters.format_group_leaderboard(rows, current_group.title or "grup ini"):
        await message.answer(chunk)
