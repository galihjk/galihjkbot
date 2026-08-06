from __future__ import annotations

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.filters.private_input import HasPendingPrivateInput
from app.filters.private_only import PrivateOnly
from app.modules.games.engine.manager import GameManager
from app.modules.games.private_input import get_private_input
from app.modules.games.router import router

NO_ACTIVE_CONTEXT_HINT = (
    "Kamu tidak punya sesi jawab yang aktif saat ini. Kalau ini soal game, "
    "buka lagi tombol yang sesuai di pesan grup ya."
)


@router.message(PrivateOnly(), HasPendingPrivateInput())
async def handle_private_game_message(
    message: Message,
    game_manager: GameManager,
    db_session: AsyncSession,
    current_user: User,
) -> None:
    """Jembatan generik: pesan privat apa pun (teks, command, media -- game
    spesifik yang menolak bentuk yang tidak sesuai) dari user yang punya
    konteks input privat aktif diteruskan ke sesi game yang bersangkutan.
    Modul ini tidak membaca/mengubah state spesifik game apa pun -- cuma
    meneruskan lewat `GameManager.handle_message()`."""
    pending = get_private_input(current_user.id)
    if pending is None:
        return  # kedaluwarsa tepat di antara filter dan handler ini -- abaikan
    await game_manager.handle_message(
        db_session,
        session_id=pending.session_id,
        message=message,
        acting_user_id=current_user.id,
    )


@router.message(PrivateOnly())
async def handle_private_message_without_context(
    message: Message,
) -> None:
    if message.text is None or message.text.startswith("/"):
        return  # bukan teks biasa, atau command -- bukan urusan modul games
    await message.answer(NO_ACTIVE_CONTEXT_HINT)
