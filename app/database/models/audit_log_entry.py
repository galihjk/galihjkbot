from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AuditLogEntry(Base):
    """Catatan aksi admin lintas-modul (enable/disable feature, reload,
    override grup, dst). Immutable -- tidak ada `updated_at`. Isi pesan
    pengguna TIDAK PERNAH disimpan di sini, hanya nilai konfigurasi."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    old_value_json: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    new_value_json: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
