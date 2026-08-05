from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GamePlayerStatus
from app.database.base import Base, TimestampMixin


class GamePlayer(Base, TimestampMixin):
    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint(
            "game_session_id", "user_id", name="uq_game_players_session_user"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=GamePlayerStatus.JOINED.value, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    eliminated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    eliminated_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
