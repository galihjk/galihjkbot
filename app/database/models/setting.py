from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Setting(Base, TimestampMixin):
    """Key-value setting runtime lintas-modul (bukan konfigurasi deployment --
    itu tetap di `app/core/config.py::Settings` lewat env). Dipakai untuk
    nilai yang berubah lewat command admin saat bot berjalan, misalnya
    `autoreply.active_rule_set_id`."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
