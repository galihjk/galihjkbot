from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AutoreplyRuleSet(Base, TimestampMixin):
    """Satu snapshot lengkap hasil sinkronisasi Google Sheet. `public_id`
    (format `ARS-000001`) diisi setelah insert, dari `id` autoincrement --
    tidak ada sequence terpisah, lihat `autoreply_repository.insert_rule_set`."""

    __tablename__ = "autoreply_rule_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str | None] = mapped_column(String(16), unique=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_etag: Mapped[str | None] = mapped_column(String(255))
    source_last_modified: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    active_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    disabled_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
