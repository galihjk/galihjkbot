from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GameStatus
from app.database.base import Base, TimestampMixin


class GameSession(Base, TimestampMixin):
    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=GameStatus.CREATED.value, nullable=False
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    lobby_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_players: Mapped[int] = mapped_column(Integer, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)
    lobby_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    starting_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    state_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
