from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.utils.datetime import utcnow


def format_uptime(started_at: datetime) -> str:
    delta = utcnow() - started_at
    total_seconds = int(delta.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} hari")
    if days or hours:
        parts.append(f"{hours} jam")
    parts.append(f"{minutes} menit")
    return " ".join(parts)


async def build_health_report(
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    started_at: datetime,
) -> str:
    try:
        await bot.get_me()
        bot_api_status = "Connected"
    except Exception:
        bot_api_status = "Error"

    try:
        await session.execute(text("SELECT 1"))
        database_status = "Healthy"
    except Exception:
        database_status = "Error"

    lines = [
        "🟢 SYSTEM HEALTH",
        f"Bot API     : {bot_api_status}",
        f"Database    : {database_status}",
        "Polling     : Running",
        f"Uptime      : {format_uptime(started_at)}",
        f"Versi       : {settings.app_version}",
        f"Environment : {settings.app_env}",
    ]
    return "\n".join(lines)
