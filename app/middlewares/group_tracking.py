from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import TelegramObject

from app.database.repositories.group_repository import (
    upsert_group,
    upsert_group_member,
)
from app.utils.telegram import extract_chat


class GroupTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = extract_chat(event)
        current_user = data.get("current_user")

        if (
            chat is not None
            and chat.type != ChatType.PRIVATE
            and current_user is not None
        ):
            session = data["db_session"]
            group = await upsert_group(session, chat)
            await upsert_group_member(session, group, current_user)
            data["current_group"] = group

        return await handler(event, data)
