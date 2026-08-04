from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GroupStatus
from app.database.base import Base, TimestampMixin


class Group(Base, TimestampMixin):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    chat_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=GroupStatus.ACTIVE.value, nullable=False
    )
    bot_joined_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
