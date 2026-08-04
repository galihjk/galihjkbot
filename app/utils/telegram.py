from __future__ import annotations

from aiogram.types import CallbackQuery, Chat, Message, TelegramObject


def extract_chat(event: TelegramObject) -> Chat | None:
    if isinstance(event, Message):
        return event.chat
    if isinstance(event, CallbackQuery) and event.message is not None:
        return event.message.chat
    return None
