from __future__ import annotations

from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.exceptions import GameNotFoundError
from app.filters.group_only import GroupOnly
from app.modules.games.engine.registry import GameRegistry
from app.modules.games.keyboards.howtoplay import (
    HOWTOPLAY_LIST_KEY,
    HowToPlayCallback,
    build_howtoplay_detail_keyboard,
    build_howtoplay_list_keyboard,
)
from app.modules.games.router import router

LIST_TEXT = "📖 Cara Main — Pilih game"


@router.message(GroupOnly(), Command("howtoplay"))
async def handle_howtoplay_command(message: Message, game_registry: GameRegistry) -> None:
    games = game_registry.get_enabled()
    if not games:
        await message.answer("Belum ada game yang tersedia.")
        return
    await message.answer(LIST_TEXT, reply_markup=build_howtoplay_list_keyboard(games))


@router.callback_query(GroupOnly(), HowToPlayCallback.filter())
async def handle_howtoplay_selection(
    callback: CallbackQuery,
    callback_data: HowToPlayCallback,
    game_registry: GameRegistry,
) -> None:
    if callback_data.game_key == HOWTOPLAY_LIST_KEY:
        games = game_registry.get_enabled()
        await callback.message.edit_text(
            LIST_TEXT, reply_markup=build_howtoplay_list_keyboard(games)
        )
        await callback.answer()
        return

    try:
        game = game_registry.get(callback_data.game_key)
    except GameNotFoundError:
        await callback.answer("Game tidak ditemukan.", show_alert=True)
        return

    await callback.message.edit_text(
        game.metadata.how_to_play, reply_markup=build_howtoplay_detail_keyboard()
    )
    await callback.answer()
