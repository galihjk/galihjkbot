from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.modules.games.engine.base_game import BaseGame

HOWTOPLAY_LIST_KEY = "_list"


class HowToPlayCallback(CallbackData, prefix="howtoplay"):
    game_key: str


def build_howtoplay_list_keyboard(games: list[BaseGame]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=game.metadata.name,
                    callback_data=HowToPlayCallback(game_key=game.metadata.key).pack(),
                )
            ]
            for game in games
        ]
    )


def build_howtoplay_detail_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Kembali",
                    callback_data=HowToPlayCallback(game_key=HOWTOPLAY_LIST_KEY).pack(),
                )
            ]
        ]
    )
