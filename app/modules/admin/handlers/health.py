from __future__ import annotations

from datetime import datetime

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.filters.admin import IsAdmin
from app.filters.private_only import PrivateOnly
from app.modules.admin.callbacks import AdminCallback
from app.modules.admin.keyboards import build_back_to_dashboard_keyboard
from app.modules.admin.router import router
from app.services.health_service import build_health_report


@router.message(PrivateOnly(), IsAdmin(), Command("health"))
async def handle_health(
    message: Message,
    bot: Bot,
    db_session: AsyncSession,
    settings: Settings,
    started_at: datetime,
) -> None:
    report = await build_health_report(bot, db_session, settings, started_at)
    await message.answer(report)


@router.callback_query(
    PrivateOnly(), IsAdmin(), AdminCallback.filter(F.action == "health")
)
async def handle_health_callback(
    callback: CallbackQuery,
    bot: Bot,
    db_session: AsyncSession,
    settings: Settings,
    started_at: datetime,
) -> None:
    report = await build_health_report(bot, db_session, settings, started_at)
    await callback.message.edit_text(
        report, reply_markup=build_back_to_dashboard_keyboard()
    )
    await callback.answer()
