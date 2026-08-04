from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.services.permission_service import resolve_admin_role


class AdminContextMiddleware(BaseMiddleware):
    def __init__(self, superadmin_ids: list[int]) -> None:
        self._superadmin_ids = set(superadmin_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        current_user = data.get("current_user")
        admin_role = None

        if current_user is not None:
            session = data["db_session"]
            admin_role = await resolve_admin_role(
                session, current_user, self._superadmin_ids
            )

        data["admin_role"] = admin_role
        return await handler(event, data)
