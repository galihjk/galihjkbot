from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AdminRole
from app.database.base import Base, TimestampMixin


class Administrator(Base, TimestampMixin):
    __tablename__ = "administrators"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(16), default=AdminRole.VIEWER.value, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
