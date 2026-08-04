from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.administrator import Administrator


async def find_admin_by_user_id(
    session: AsyncSession, user_id: int
) -> Administrator | None:
    result = await session.execute(
        select(Administrator).where(Administrator.user_id == user_id)
    )
    return result.scalar_one_or_none()
