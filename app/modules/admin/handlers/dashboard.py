from __future__ import annotations

from datetime import datetime

from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.filters.admin import IsAdmin
from app.filters.private_only import PrivateOnly
from app.modules.admin.callbacks import AdminCallback
from app.modules.admin.keyboards import build_dashboard_keyboard
from app.modules.admin.presenters import format_dashboard
from app.modules.admin.router import router
from app.services.dashboard_service import build_dashboard_stats
from app.services.health_service import format_uptime


async def _render_dashboard(
    session: AsyncSession, settings: Settings, started_at: datetime
) -> str:
    stats = await build_dashboard_stats(session)
    return format_dashboard(stats, format_uptime(started_at), settings)


@router.message(PrivateOnly(), IsAdmin(), Command("admin", "dashboard"))
async def handle_admin_menu(
    message: Message,
    db_session: AsyncSession,
    settings: Settings,
    started_at: datetime,
) -> None:
    text = await _render_dashboard(db_session, settings, started_at)
    await message.answer(text, reply_markup=build_dashboard_keyboard())


@router.callback_query(
    PrivateOnly(), IsAdmin(), AdminCallback.filter(F.action == "dashboard")
)
async def handle_dashboard_refresh(
    callback: CallbackQuery,
    db_session: AsyncSession,
    settings: Settings,
    started_at: datetime,
) -> None:
    text = await _render_dashboard(db_session, settings, started_at)
    await callback.message.edit_text(text, reply_markup=build_dashboard_keyboard())
    await callback.answer()
