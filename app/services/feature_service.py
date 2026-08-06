from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.group import Group
from app.database.repositories.feature_repository import (
    get_feature,
    get_group_feature,
)


async def is_enabled(
    session: AsyncSession, feature_key: str, group: Group | None
) -> bool:
    """Group override menang atas nilai global; kalau feature belum pernah
    didaftarkan sama sekali (belum ada baris di `features`), fail-closed
    (False) -- lebih aman daripada diam-diam aktif."""
    feature = await get_feature(session, feature_key)
    if feature is None:
        return False

    if group is not None:
        override = await get_group_feature(session, group.id, feature_key)
        if override is not None:
            return override.enabled

    return feature.enabled_globally
