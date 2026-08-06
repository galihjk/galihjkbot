from __future__ import annotations

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


@router.message(Command("skor"))
async def handle_skor(
    message: Message,
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
    await message.answer(
        presenters.format_own_score(
            global_total, group_total, current_group.title if current_group else None
        )
    )


@router.message(Command("leaderboard"))
async def handle_leaderboard(
    message: Message, db_session: AsyncSession, settings: Settings
) -> None:
    start, end, _ = period.current_period_window(settings.timezone)
    rows = await leaderboard_repository.sum_global_scores_by_user(db_session, start, end)
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
