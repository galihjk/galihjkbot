from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.database.models.user import User
from app.database.repositories.admin_repository import find_admin_by_user_id

_ROLE_LEVELS = {
    AdminRole.VIEWER: 1,
    AdminRole.OPERATOR: 2,
    AdminRole.ADMIN: 3,
    AdminRole.SUPERADMIN: 4,
}


def has_minimum_role(current: AdminRole | None, minimum: AdminRole) -> bool:
    if current is None:
        return False
    return _ROLE_LEVELS[current] >= _ROLE_LEVELS[minimum]


async def resolve_admin_role(
    session: AsyncSession,
    user: User,
    superadmin_ids: set[int],
) -> AdminRole | None:
    if user.telegram_user_id in superadmin_ids:
        return AdminRole.SUPERADMIN

    admin = await find_admin_by_user_id(session, user.id)
    if admin is not None and admin.enabled:
        return AdminRole(admin.role)

    return None
