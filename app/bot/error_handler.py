from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import ErrorEvent, Message

from app.core.config import Settings
from app.utils.errors import generate_error_reference

logger = logging.getLogger(__name__)

USER_FACING_MESSAGE = (
    "Terjadi kesalahan pada bot.\n"
    "Referensi: {reference}\n"
    "Sudah tercatat, silakan coba lagi sebentar."
)


def _extract_reply_target(event: ErrorEvent) -> Message | None:
    update = event.update
    if update.message is not None:
        return update.message
    if update.callback_query is not None and update.callback_query.message is not None:
        return update.callback_query.message
    return None


async def handle_global_error(event: ErrorEvent, bot: Bot, settings: Settings) -> None:
    reference = generate_error_reference()
    logger.exception(
        "Unhandled update. reference=%s update_id=%s",
        reference,
        event.update.update_id,
        exc_info=event.exception,
    )

    target = _extract_reply_target(event)
    if target is not None:
        try:
            await target.answer(USER_FACING_MESSAGE.format(reference=reference))
        except Exception:
            logger.exception(
                "Gagal mengirim pesan error ke chat, reference=%s", reference
            )

    for superadmin_id in settings.telegram_superadmin_ids:
        try:
            await bot.send_message(
                superadmin_id,
                f"⚠️ Error {reference}\n{type(event.exception).__name__}: {event.exception}",
            )
        except Exception:
            logger.exception(
                "Gagal mengirim notifikasi error ke superadmin %s, reference=%s",
                superadmin_id,
                reference,
            )
