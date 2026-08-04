from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.modules.games.engine.base_game import BaseGame


class GameMenuCallback(CallbackData, prefix="gamemenu"):
    game_key: str


def build_game_menu_keyboard(games: list[BaseGame]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=game.metadata.name,
                    callback_data=GameMenuCallback(game_key=game.metadata.key).pack(),
                )
            ]
            for game in games
        ]
    )
