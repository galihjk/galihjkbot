from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.modules.games.callbacks import GameCallback

MAX_NAME_LENGTH = 10


def _truncate(name: str) -> str:
    return name if len(name) <= MAX_NAME_LENGTH else name[: MAX_NAME_LENGTH - 1] + "…"


def build_seat_keyboard(
    session_id: int,
    round_number: int,
    seat_total: int,
    seats: dict[str, int],
    players_by_id: dict[int, str],
    contests: dict[str, dict] | None = None,
) -> InlineKeyboardMarkup:
    contests = contests or {}
    buttons = []
    for number in range(1, seat_total + 1):
        holder_id = seats.get(str(number))
        if holder_id is not None:
            holder_name = players_by_id.get(holder_id, "?")
            text = f"🪑 {number} · {_truncate(holder_name)}"
        elif str(number) in contests:
            text = f"🔥 {number} · Diperebutkan"
        else:
            text = f"🪑 {number}"
        buttons.append(
            InlineKeyboardButton(
                text=text,
                callback_data=GameCallback(
                    session_id=session_id, data=f"{round_number}-{number}"
                ).pack(),
            )
        )

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)
