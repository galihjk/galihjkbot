from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AutoreplySyncRun(Base, TimestampMixin):
    __tablename__ = "autoreply_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str | None] = mapped_column(String(16), unique=True)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    source_checksum: Mapped[str | None] = mapped_column(String(64))
    total_rows: Mapped[int | None] = mapped_column(Integer)
    active_rows: Mapped[int | None] = mapped_column(Integer)
    disabled_rows: Mapped[int | None] = mapped_column(Integer)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_reference: Mapped[str | None] = mapped_column(String(32))
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
