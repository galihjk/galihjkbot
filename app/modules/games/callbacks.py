from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class GameCallback(CallbackData, prefix="game"):
    """Callback generik untuk aksi dalam-game. `data` bebas ditentukan tiap game
    (misal nomor kursi) dan diparse ulang oleh implementasi game itu sendiri."""

    session_id: int
    data: str
