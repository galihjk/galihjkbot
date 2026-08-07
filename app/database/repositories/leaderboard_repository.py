from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.administrator import Administrator
from app.database.models.game_session import GameSession
from app.database.models.group import Group
from app.database.models.monthly_maintenance_run import MonthlyMaintenanceRun
from app.database.models.user import User
from app.database.models.user_game_score import UserGameScore


async def sum_user_score(
    session: AsyncSession, user_id: int, start: datetime, end: datetime
) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(UserGameScore.final_score), 0)).where(
            UserGameScore.user_id == user_id,
            UserGameScore.committed_at >= start,
            UserGameScore.committed_at < end,
        )
    )
    return result.scalar_one()


async def sum_user_score_in_group(
    session: AsyncSession, user_id: int, group_id: int, start: datetime, end: datetime
) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(UserGameScore.final_score), 0))
        .join(GameSession, GameSession.id == UserGameScore.session_id)
        .where(
            UserGameScore.user_id == user_id,
            GameSession.group_id == group_id,
            UserGameScore.committed_at >= start,
            UserGameScore.committed_at < end,
        )
    )
    return result.scalar_one()


async def sum_global_scores_by_user(
    session: AsyncSession, start: datetime, end: datetime
) -> list[tuple[User, int]]:
    total = func.sum(UserGameScore.final_score).label("total")
    result = await session.execute(
        select(User, total)
        .join(User, User.id == UserGameScore.user_id)
        .where(
            UserGameScore.committed_at >= start,
            UserGameScore.committed_at < end,
        )
        .group_by(User.id)
        .order_by(total.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def sum_global_scores_by_user_subscribed(
    session: AsyncSession, start: datetime, end: datetime
) -> list[tuple[User, int]]:
    """Sama seperti `sum_global_scores_by_user`, tapi cuma user dengan cache
    `is_leaderboard_channel_subscribed=True` -- dipakai `/leaderboard` on-demand
    supaya konsisten dengan pengumuman channel bulanan (yang cuma memuat
    subscriber). Job bulanan sendiri TIDAK memakai fungsi ini -- dia re-verify
    live lalu memfilter sendiri dari hasil `sum_global_scores_by_user` mentah."""
    total = func.sum(UserGameScore.final_score).label("total")
    result = await session.execute(
        select(User, total)
        .join(User, User.id == UserGameScore.user_id)
        .where(
            UserGameScore.committed_at >= start,
            UserGameScore.committed_at < end,
            User.is_leaderboard_channel_subscribed.is_(True),
        )
        .group_by(User.id)
        .order_by(total.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def set_channel_subscription(
    session: AsyncSession, user_id: int, is_subscribed: bool
) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_leaderboard_channel_subscribed=is_subscribed)
    )


async def sum_group_scores_by_user(
    session: AsyncSession, group_id: int, start: datetime, end: datetime
) -> list[tuple[User, int]]:
    total = func.sum(UserGameScore.final_score).label("total")
    result = await session.execute(
        select(User, total)
        .join(User, User.id == UserGameScore.user_id)
        .join(GameSession, GameSession.id == UserGameScore.session_id)
        .where(
            GameSession.group_id == group_id,
            UserGameScore.committed_at >= start,
            UserGameScore.committed_at < end,
        )
        .group_by(User.id)
        .order_by(total.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def sum_scores_by_group(
    session: AsyncSession, start: datetime, end: datetime
) -> list[tuple[Group, int]]:
    """Leaderboard ANTAR-GRUP -- total skor yang dikumpulkan tiap grup,
    diurutkan tertinggi ke terendah (jadi ranking bergengsi, bukan cuma
    daftar), dipakai utk pengumuman di channel."""
    total = func.sum(UserGameScore.final_score).label("total")
    result = await session.execute(
        select(Group, total)
        .join(GameSession, GameSession.group_id == Group.id)
        .join(UserGameScore, UserGameScore.session_id == GameSession.id)
        .where(
            UserGameScore.committed_at >= start,
            UserGameScore.committed_at < end,
        )
        .group_by(Group.id)
        .order_by(total.desc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def delete_scores_in_range(
    session: AsyncSession, start: datetime, end: datetime
) -> int:
    result = await session.execute(
        delete(UserGameScore).where(
            UserGameScore.committed_at >= start,
            UserGameScore.committed_at < end,
        )
    )
    return result.rowcount or 0


async def find_inactive_non_admin_users(
    session: AsyncSession, threshold: datetime
) -> list[User]:
    """Kandidat penghapusan user tidak aktif -- pengecualian admin lewat
    tabel `administrators` (aktif) sudah difilter di sini; pengecualian
    superadmin env (`Settings.telegram_superadmin_ids`) HARUS difilter
    tambahan di service layer karena butuh akses env, bukan query DB."""
    admin_user_ids = select(Administrator.user_id).where(Administrator.enabled.is_(True))
    result = await session.execute(
        select(User).where(
            User.last_seen_at < threshold,
            User.id.not_in(admin_user_ids),
        )
    )
    return list(result.scalars().all())


async def find_inactive_groups(session: AsyncSession, threshold: datetime) -> list[Group]:
    result = await session.execute(
        select(Group).where(Group.last_activity_at < threshold)
    )
    return list(result.scalars().all())


async def delete_users_by_ids(session: AsyncSession, user_ids: list[int]) -> int:
    if not user_ids:
        return 0
    result = await session.execute(delete(User).where(User.id.in_(user_ids)))
    return result.rowcount or 0


async def delete_groups_by_ids(session: AsyncSession, group_ids: list[int]) -> int:
    if not group_ids:
        return 0
    result = await session.execute(delete(Group).where(Group.id.in_(group_ids)))
    return result.rowcount or 0


async def has_run(session: AsyncSession, period: str) -> bool:
    result = await session.execute(
        select(MonthlyMaintenanceRun.period).where(
            MonthlyMaintenanceRun.period == period
        )
    )
    return result.scalar_one_or_none() is not None


async def mark_run(session: AsyncSession, period: str, run_at: datetime) -> None:
    session.add(MonthlyMaintenanceRun(period=period, run_at=run_at))
    await session.flush()
