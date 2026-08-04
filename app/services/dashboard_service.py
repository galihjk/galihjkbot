from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.group_repository import count_groups
from app.database.repositories.user_repository import count_active_since, count_users
from app.utils.datetime import utcnow


@dataclass(frozen=True)
class DashboardStats:
    total_users: int
    active_users_24h: int
    total_groups: int


async def build_dashboard_stats(session: AsyncSession) -> DashboardStats:
    since = utcnow() - timedelta(hours=24)
    return DashboardStats(
        total_users=await count_users(session),
        active_users_24h=await count_active_since(session, since),
        total_groups=await count_groups(session),
    )
