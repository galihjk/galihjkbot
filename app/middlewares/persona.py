from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.repositories.user_repository import get_or_create_virtual_player
from app.services.permission_service import resolve_admin_role
from app.utils.telegram import extract_chat


class PersonaMiddleware(BaseMiddleware):
    """Izinkan admin "berperan" sebagai virtual player untuk testing game
    solo (lihat command /p1../p7 dan /p0 di modul devtools).

    PENTING: instance ini harus DIBAGI (bukan dibuat ulang) antara observer
    message dan callback_query, supaya switch lewat command terlihat oleh
    klik tombol juga. State-nya sengaja in-memory saja (reset saat restart)
    karena ini murni alat bantu development, bukan fitur produksi.
    """

    def __init__(self, superadmin_ids: list[int]) -> None:
        self._superadmin_ids = set(superadmin_ids)
        self._active: dict[tuple[int, int], int] = {}

    def set_persona(self, chat_id: int, real_telegram_id: int, index: int) -> None:
        self._active[(chat_id, real_telegram_id)] = index

    def clear(self, chat_id: int, real_telegram_id: int) -> None:
        self._active.pop((chat_id, real_telegram_id), None)

    def get_active(self, chat_id: int, real_telegram_id: int) -> int | None:
        return self._active.get((chat_id, real_telegram_id))

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        real_user = data.get("current_user")
        data["real_user"] = real_user

        if real_user is None:
            data["real_admin_role"] = None
            return await handler(event, data)

        data["real_admin_role"] = await resolve_admin_role(
            data["db_session"], real_user, self._superadmin_ids
        )

        chat = extract_chat(event)
        if chat is not None:
            index = self.get_active(chat.id, real_user.telegram_user_id)
            if index is not None:
                data["current_user"] = await get_or_create_virtual_player(
                    data["db_session"], index
                )

        return await handler(event, data)
