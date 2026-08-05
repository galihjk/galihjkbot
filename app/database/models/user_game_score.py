from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class UserGameScore(Base, TimestampMixin):
    __tablename__ = "user_game_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_key: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    result_score: Mapped[int] = mapped_column(Integer, nullable=False)
    participation_score: Mapped[int] = mapped_column(Integer, nullable=False)
    survival_score: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
