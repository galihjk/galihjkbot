from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from app.core.enums import AdminRole
from app.services.permission_service import has_minimum_role


class IsAdmin(BaseFilter):
    def __init__(self, minimum: AdminRole = AdminRole.VIEWER) -> None:
        self.minimum = minimum

    async def __call__(
        self,
        event: TelegramObject,
        admin_role: AdminRole | None = None,
    ) -> bool:
        return has_minimum_role(admin_role, self.minimum)
