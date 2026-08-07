from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from aiogram.types import Chat
from aiogram.types import Message as AiogramMessage
from aiogram.types import User as TgUser

from app.modules.devtools.router import get_router as get_devtools_router
from app.modules.games.private_input import register_private_input
from app.modules.games.router import get_router as get_games_router


def _make_private_command_message(text: str) -> AiogramMessage:
    chat = Chat(id=1, type="private")
    from_user = TgUser(id=1, is_bot=False, first_name="Admin")
    return AiogramMessage(message_id=1, date=datetime.now(), chat=chat, from_user=from_user, text=text)


def _find_handler(router, func_name: str):
    for handler in router.message.handlers:
        if handler.callback.__name__ == func_name:
            return handler
    raise AssertionError(f"handler {func_name} tidak ditemukan di router {router.name}")


async def test_persona_switch_filter_matches_private_chat():
    """Regresi: /p0../p7 sempat cuma bisa dipakai di grup (`GroupOnly()`),
    padahal admin butuh switch persona di chat PRIVATnya sendiri juga supaya
    bisa uji game yang butuh interaksi DM (Kuis Kenal) lewat virtual player."""
    handler = _find_handler(get_devtools_router(), "handle_persona_switch")
    message = _make_private_command_message("/p3")

    matched, _ = await handler.check(message, bot=SimpleNamespace(id=1))
    assert matched is True


async def test_games_private_bridge_would_also_match_pending_context():
    """Sanity check bahwa konfliknya NYATA (bukan cuma teoretis): handler
    pesan privat generik games JUGA cocok untuk pesan berbentuk command
    kalau pengirim sedang punya konteks input privat aktif -- ia sengaja
    TIDAK skip command (beda dari sibling-nya `handle_private_message_without_context`),
    supaya game bisa menolaknya sebagai "command, bukan jawaban" (§14 desain).
    Ini yang membuat urutan router di test berikutnya genuinely penting."""
    handler = _find_handler(get_games_router(), "handle_private_game_message")
    message = _make_private_command_message("/p3")
    user = SimpleNamespace(id=555)
    register_private_input(
        user_id=user.id, session_id=1, purpose="answer", round_number=1,
        nonce="x", ttl_seconds=60,
    )

    matched, _ = await handler.check(message, current_user=user)
    assert matched is True


def test_devtools_router_registered_before_games_router(registered_dispatcher):
    """Bukti bahwa perbaikan urutan `register_modules()` benar-benar berlaku:
    aiogram memilih match PERTAMA berdasarkan urutan `include_router()`
    (sub-router dicoba berurutan, berhenti di non-UNHANDLED pertama) -- jadi
    urutan register di sini adalah satu-satunya hal yang mencegah command
    persona "ditelan" oleh handler pesan privat generik games (lihat dua
    test di atas: keduanya SAMA-SAMA cocok untuk skenario yang sama)."""
    router_names = [router.name for router in registered_dispatcher.sub_routers]
    assert router_names.index("devtools") < router_names.index("games")
