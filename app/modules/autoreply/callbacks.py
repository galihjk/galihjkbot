from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class AutoreplyCallback(CallbackData, prefix="msgcmd"):
    action: str
