from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class GameEvent(Base, TimestampMixin):
    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
