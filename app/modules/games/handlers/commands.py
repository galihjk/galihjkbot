from __future__ import annotations

from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.core.exceptions import ActiveGameExistsError, GameNotFoundError, InvalidGameStateError
from app.database.models.group import Group
from app.database.models.user import User
from app.database.repositories.game_repository import count_active_players, find_active_by_group
from app.filters.group_only import GroupOnly
from app.modules.games.engine.manager import GameManager
from app.modules.games.engine.registry import GameRegistry
from app.modules.games.keyboards.game_menu import GameMenuCallback, build_game_menu_keyboard
from app.modules.games.presenters import format_game_status
from app.modules.games.router import router


@router.message(GroupOnly(), Command("games"))
async def handle_list_games(message: Message, game_registry: GameRegistry) -> None:
    games = game_registry.get_enabled()
    if not games:
        await message.answer("Belum ada game yang aktif.")
        return

    lines = ["🎮 DAFTAR GAME"]
    lines.extend(f"- {game.metadata.name}: {game.metadata.description}" for game in games)
    await message.answer("\n".join(lines))


@router.message(GroupOnly(), Command("game"))
async def handle_game_command(
    message: Message,
    command: CommandObject,
    game_registry: GameRegistry,
    game_manager: GameManager,
    db_session: AsyncSession,
    current_user: User,
    current_group: Group,
) -> None:
    game_key = (command.args or "").strip()

    if not game_key:
        games = game_registry.get_enabled()
        if not games:
            await message.answer("Belum ada game yang tersedia.")
            return
        await message.answer("🎮 Pilih Game", reply_markup=build_game_menu_keyboard(games))
        return

    try:
        await game_manager.create_lobby(
            db_session,
            group_id=current_group.id,
            telegram_chat_id=current_group.telegram_chat_id,
            game_key=game_key,
            created_by_user_id=current_user.id,
        )
    except GameNotFoundError:
        await message.answer("Game tidak ditemukan.")
    except ActiveGameExistsError:
        await message.answer(
            "Sudah ada game aktif di grup ini. Gunakan /gamestatus untuk melihat."
        )


@router.callback_query(GroupOnly(), GameMenuCallback.filter())
async def handle_game_menu_selection(
    callback: CallbackQuery,
    callback_data: GameMenuCallback,
    game_manager: GameManager,
    db_session: AsyncSession,
    current_user: User,
    current_group: Group,
) -> None:
    try:
        await game_manager.create_lobby(
            db_session,
            group_id=current_group.id,
            telegram_chat_id=current_group.telegram_chat_id,
            game_key=callback_data.game_key,
            created_by_user_id=current_user.id,
        )
        await callback.message.edit_text("✅ Lobby dibuat di bawah.")
        await callback.answer()
    except GameNotFoundError:
        await callback.answer("Game tidak ditemukan.", show_alert=True)
    except ActiveGameExistsError:
        await callback.answer("Sudah ada game aktif di grup ini.", show_alert=True)


@router.message(GroupOnly(), Command("gamestatus"))
async def handle_game_status(
    message: Message,
    db_session: AsyncSession,
    current_group: Group,
    game_registry: GameRegistry,
) -> None:
    game_session = await find_active_by_group(db_session, current_group.id)
    if game_session is None:
        await message.answer("Tidak ada game aktif di grup ini.")
        return

    game = game_registry.get(game_session.game_key)
    player_count = await count_active_players(db_session, game_session.id)
    await message.answer(format_game_status(game_session, game.metadata, player_count))


@router.message(GroupOnly(), Command("cancelgame"))
async def handle_cancel_game(
    message: Message,
    db_session: AsyncSession,
    current_group: Group,
    current_user: User,
    game_manager: GameManager,
    admin_role: AdminRole | None = None,
) -> None:
    game_session = await find_active_by_group(db_session, current_group.id)
    if game_session is None:
        await message.answer("Tidak ada game aktif di grup ini.")
        return

    is_creator = game_session.created_by_user_id == current_user.id
    if not (is_creator or admin_role is not None):
        await message.answer("Hanya pembuat game atau admin yang bisa membatalkan.")
        return

    try:
        await game_manager.cancel_game(
            db_session,
            session_id=game_session.id,
            reason="Dibatalkan lewat /cancelgame",
            cancelled_by_user_id=current_user.id,
        )
        await message.answer("Game dibatalkan.")
    except InvalidGameStateError:
        await message.answer("Game tidak bisa dibatalkan saat ini.")
