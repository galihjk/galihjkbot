from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import UserStatus
from app.database.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(8))
    is_bot: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=UserStatus.ACTIVE.value, nullable=False
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
