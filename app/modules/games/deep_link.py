from __future__ import annotations

from typing import Any

from aiogram.filters import CommandObject

from app.database.models.user import User
from app.modules.games.engine.manager import GameManager
from app.modules.games.engine.registry import GameRegistry


async def try_handle_game_deep_link(
    message: Any,
    command: CommandObject,
    *,
    db_session: Any,
    current_user: User,
    game_registry: GameRegistry,
    game_manager: GameManager,
) -> bool:
    """Coba tangani payload `/start <payload>` sebagai deep link dalam-game.

    Return `True` kalau payload dikenali (dan sudah ditangani lewat
    `BaseGame.handle_deep_link`, sukses atau ditolak dengan pesan error --
    keduanya "sudah ditangani"), `False` kalau payload bukan urusan game apa
    pun sama sekali supaya `/start` polos tetap berjalan seperti biasa.
    """
    payload = command.args
    if not payload:
        return False

    game = game_registry.find_by_deep_link_prefix(payload)
    if game is None:
        return False

    await game.handle_deep_link(
        payload,
        message=message,
        db_session=db_session,
        acting_user_id=current_user.id,
        game_manager=game_manager,
    )
    return True
