from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class GroupMember(Base, TimestampMixin):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
