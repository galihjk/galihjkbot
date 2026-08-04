from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.repositories.user_repository import upsert_user


class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = getattr(event, "from_user", None)
        if telegram_user is not None and not telegram_user.is_bot:
            session = data["db_session"]
            data["current_user"] = await upsert_user(session, telegram_user)

        return await handler(event, data)
