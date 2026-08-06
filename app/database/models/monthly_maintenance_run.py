from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MonthlyMaintenanceRun(Base):
    """Marker idempotensi untuk job pemeliharaan bulanan (leaderboard+reset
    skor, pembersihan user/grup tidak aktif) -- pola exists-check yang sama
    seperti `UserGameScore`/`commit_scores`, bukan kolom timestamp terpisah.
    `period` berformat "YYYY-MM" (bulan yang SUDAH diproses, bukan bulan
    berjalan)."""

    __tablename__ = "monthly_maintenance_runs"

    period: Mapped[str] = mapped_column(String(7), primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
