from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.game_session import GameSession

if TYPE_CHECKING:
    from app.modules.games.engine.manager import GameManager


@dataclass(frozen=True)
class PlayerInfo:
    user_id: int
    telegram_user_id: int
    display_name: str


@dataclass
class GameContext:
    bot: Bot
    db_session: AsyncSession
    game_session: GameSession
    telegram_chat_id: int
    game_manager: "GameManager"
    active_players: list[PlayerInfo] = field(default_factory=list)

    @property
    def session_id(self) -> int:
        return self.game_session.id
