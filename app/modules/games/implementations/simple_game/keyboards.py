from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.modules.games.callbacks import GameCallback


def build_seat_keyboard(
    session_id: int, available_seat_numbers: list[int]
) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=f"🪑 Kursi {number}",
            callback_data=GameCallback(session_id=session_id, data=str(number)).pack(),
        )
        for number in available_seat_numbers
    ]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)
