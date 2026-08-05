from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class LobbyCallback(CallbackData, prefix="lobby"):
    session_id: int
    action: str


def build_lobby_keyboard(session_id: int) -> InlineKeyboardMarkup:
    def _btn(text: str, action: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=text,
            callback_data=LobbyCallback(session_id=session_id, action=action).pack(),
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("➕ Gabung", "join"), _btn("➖ Keluar", "leave")],
            [_btn("⏱ Extend", "extend")],
            [_btn("🚀 Force Start", "force_start")],
            [_btn("❌ Batalkan", "cancel")],
        ]
    )


def build_ready_check_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Siap",
                    callback_data=LobbyCallback(
                        session_id=session_id, action="ready"
                    ).pack(),
                )
            ],
        ]
    )
