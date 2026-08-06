from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.modules.autoreply.callbacks import AutoreplyCallback


def build_panel_keyboard(feature_enabled: bool) -> InlineKeyboardMarkup:
    toggle_button = (
        InlineKeyboardButton(
            text="⏸ Nonaktifkan",
            callback_data=AutoreplyCallback(action="disable").pack(),
        )
        if feature_enabled
        else InlineKeyboardButton(
            text="▶ Aktifkan",
            callback_data=AutoreplyCallback(action="enable").pack(),
        )
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Reload",
                    callback_data=AutoreplyCallback(action="reload").pack(),
                ),
                InlineKeyboardButton(
                    text="📖 Format",
                    callback_data=AutoreplyCallback(action="format").pack(),
                ),
            ],
            [toggle_button],
        ]
    )
