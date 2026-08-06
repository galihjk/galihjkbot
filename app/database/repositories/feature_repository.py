from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.feature import Feature
from app.database.models.group_feature import GroupFeature


async def get_feature(session: AsyncSession, feature_key: str) -> Feature | None:
    result = await session.execute(
        select(Feature).where(Feature.feature_key == feature_key)
    )
    return result.scalar_one_or_none()


async def set_feature_enabled(
    session: AsyncSession, feature_key: str, enabled: bool
) -> Feature:
    feature = await get_feature(session, feature_key)
    if feature is None:
        feature = Feature(feature_key=feature_key, enabled_globally=enabled)
        session.add(feature)
    else:
        feature.enabled_globally = enabled
    await session.flush()
    return feature


async def get_group_feature(
    session: AsyncSession, group_id: int, feature_key: str
) -> GroupFeature | None:
    result = await session.execute(
        select(GroupFeature).where(
            GroupFeature.group_id == group_id,
            GroupFeature.feature_key == feature_key,
        )
    )
    return result.scalar_one_or_none()


async def set_group_feature(
    session: AsyncSession, group_id: int, feature_key: str, enabled: bool
) -> GroupFeature:
    group_feature = await get_group_feature(session, group_id, feature_key)
    if group_feature is None:
        group_feature = GroupFeature(
            group_id=group_id, feature_key=feature_key, enabled=enabled
        )
        session.add(group_feature)
    else:
        group_feature.enabled = enabled
    await session.flush()
    return group_feature


async def clear_group_feature(
    session: AsyncSession, group_id: int, feature_key: str
) -> None:
    group_feature = await get_group_feature(session, group_id, feature_key)
    if group_feature is not None:
        await session.delete(group_feature)
        await session.flush()
