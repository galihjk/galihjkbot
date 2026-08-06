from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from app.database.models.user import User
from app.modules.games.private_input import get_private_input


class HasPendingPrivateInput(BaseFilter):
    async def __call__(self, event: TelegramObject, current_user: User) -> bool:
        return get_private_input(current_user.id) is not None
