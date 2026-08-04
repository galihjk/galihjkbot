from __future__ import annotations

from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from app.utils.telegram import extract_chat


class GroupOnly(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        chat = extract_chat(event)
        return chat is not None and chat.type != ChatType.PRIVATE
