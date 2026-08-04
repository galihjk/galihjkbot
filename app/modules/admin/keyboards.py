from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.modules.admin.callbacks import AdminCallback


def build_dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Pengguna",
                    callback_data=AdminCallback(action="users").pack(),
                ),
                InlineKeyboardButton(
                    text="🏘 Grup",
                    callback_data=AdminCallback(action="groups").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🩺 Kesehatan",
                    callback_data=AdminCallback(action="health").pack(),
                ),
                InlineKeyboardButton(
                    text="🔄 Refresh",
                    callback_data=AdminCallback(action="dashboard").pack(),
                ),
            ],
        ]
    )


def build_back_to_dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅ Kembali",
                    callback_data=AdminCallback(action="dashboard").pack(),
                )
            ],
        ]
    )
