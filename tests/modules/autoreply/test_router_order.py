from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from aiogram.types import Chat
from aiogram.types import Message as AiogramMessage
from aiogram.types import User as TgUser

from app.core.enums import AdminRole
from app.modules.autoreply.admin_router import get_router as get_autoreply_admin_router
from app.modules.games.router import get_router as get_games_router


def _make_private_command_message(text: str) -> AiogramMessage:
    chat = Chat(id=1, type="private")
    from_user = TgUser(id=1, is_bot=False, first_name="Admin")
    return AiogramMessage(
        message_id=1, date=datetime.now(), chat=chat, from_user=from_user, text=text
    )


def _find_handler(router, func_name: str):
    for handler in router.message.handlers:
        if handler.callback.__name__ == func_name:
            return handler
    raise AssertionError(f"handler {func_name} tidak ditemukan di router {router.name}")


async def test_msgcmd_status_filter_matches_for_admin_in_private_chat():
    handler = _find_handler(get_autoreply_admin_router(), "handle_status")
    message = _make_private_command_message("/msgcmd_status")

    matched, _ = await handler.check(
        message, admin_role=AdminRole.SUPERADMIN, bot=SimpleNamespace(id=1)
    )
    assert matched is True


async def test_games_private_catchall_would_also_match_same_message():
    """Bukti konflik NYATA (bukan teoretis): `handle_private_message_without_context`
    di modul `games` filternya cuma `PrivateOnly()` -- cocok untuk SEMUA
    pesan privat termasuk command, `startswith("/")` baru dicek di DALAM
    body (bukan filter). Ini yang membuat urutan router di test berikutnya
    genuinely penting -- bug nyata: /msgcmd_status dkk tidak pernah dibalas
    sebelum `autoreply_admin` dipindah sebelum `games` (2026-08-07)."""
    handler = _find_handler(get_games_router(), "handle_private_message_without_context")
    message = _make_private_command_message("/msgcmd_status")

    matched, _ = await handler.check(message)
    assert matched is True


def test_autoreply_admin_router_registered_before_games_router(registered_dispatcher):
    router_names = [router.name for router in registered_dispatcher.sub_routers]
    assert router_names.index("autoreply_admin") < router_names.index("games")
