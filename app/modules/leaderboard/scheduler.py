from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.maintenance import MaintenanceGate
from app.modules.leaderboard.service import run_monthly_maintenance

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 24 * 60 * 60


async def run_forever(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    maintenance_gate: MaintenanceGate,
) -> None:
    """Loop `asyncio` ringan, TANPA dependency scheduler tambahan (sesuai
    filosofi minim-dependency project, penting utk Termux). Cek 1x/hari
    cukup -- job-nya sendiri idempoten lewat marker `monthly_maintenance_runs`,
    jadi kalau bot mati pas tanggal 1, begitu nyala lagi langsung ketahuan
    dari marker yang belum ada (tahan downtime)."""
    while True:
        try:
            await run_monthly_maintenance(bot, session_factory, settings, maintenance_gate)
        except Exception:
            logger.exception("Job pemeliharaan bulanan gagal tak terduga.")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
