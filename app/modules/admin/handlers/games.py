from __future__ import annotations

from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.game_repository import (
    count_active_players,
    find_all_active,
    find_by_id,
)
from app.database.repositories.group_repository import find_by_id as find_group_by_id
from app.filters.admin import IsAdmin
from app.filters.private_only import PrivateOnly
from app.modules.admin.presenters import format_active_games_list, format_game_info_detail
from app.modules.admin.router import router
from app.modules.games.engine.registry import GameRegistry


@router.message(PrivateOnly(), IsAdmin(), Command("activegames"))
async def handle_active_games(
    message: Message,
    db_session: AsyncSession,
    game_registry: GameRegistry,
) -> None:
    sessions = await find_all_active(db_session)
    rows = []
    for game_session in sessions:
        group = await find_group_by_id(db_session, game_session.group_id)
        game = game_registry.get(game_session.game_key)
        player_count = await count_active_players(db_session, game_session.id)
        rows.append((game_session, group, game.metadata.name, player_count))

    await message.answer(format_active_games_list(rows))


@router.message(PrivateOnly(), IsAdmin(), Command("gameinfo"))
async def handle_game_info(
    message: Message,
    command: CommandObject,
    db_session: AsyncSession,
    game_registry: GameRegistry,
) -> None:
    identifier = (command.args or "").strip()
    if not identifier or not identifier.isdigit():
        await message.answer("Gunakan: /gameinfo <session_id>")
        return

    game_session = await find_by_id(db_session, int(identifier))
    if game_session is None:
        await message.answer("Sesi tidak ditemukan.")
        return

    group = await find_group_by_id(db_session, game_session.group_id)
    game = game_registry.get(game_session.game_key)
    player_count = await count_active_players(db_session, game_session.id)
    await message.answer(
        format_game_info_detail(game_session, group, game.metadata, player_count)
    )
