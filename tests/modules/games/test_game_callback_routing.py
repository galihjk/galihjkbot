from __future__ import annotations

from datetime import datetime

from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Chat
from aiogram.types import Message as AiogramMessage
from aiogram.types import User as TgUser

from app.modules.games.callbacks import GameCallback
from app.modules.games.router import get_router


def _make_callback_query(chat_type: str) -> CallbackQuery:
    chat = Chat(id=1, type=chat_type)
    message = AiogramMessage(message_id=1, date=datetime.now(), chat=chat, from_user=None)
    from_user = TgUser(id=1, is_bot=False, first_name="Test")
    data = GameCallback(session_id=1, data="1-1-qp-0").pack()
    return CallbackQuery(id="1", from_user=from_user, chat_instance="x", message=message, data=data)


def _find_game_callback_handler():
    """Ambil `HandlerObject` yang mendaftar untuk `GameCallback` di router
    `games` sungguhan -- BUKAN memanggil `GameManager` langsung, supaya bug
    di filter routing (mis. `GroupOnly()` yang salah dipasang) benar-benar
    tertangkap, bukan cuma logic di dalam game itu sendiri."""
    router = get_router()
    for handler in router.callback_query.handlers:
        if handler.callback.__name__ == "handle_game_callback":
            return handler
    raise AssertionError("handler handle_game_callback tidak ditemukan di router games")


async def test_game_callback_is_reachable_from_private_chat():
    """Regresi: tombol dalam-game yang dikirim ke CHAT PRIVAT (mis. tombol
    pilih soal Kuis Kenal) sempat tidak pernah tersampaikan ke game manapun
    karena handler generik `handle_game_callback` difilter `GroupOnly()` --
    filter itu cocok untuk Kursi Kosong (semua tombolnya di grup) tapi salah
    untuk game apa pun yang taruh tombol di private chat. Test ini gagal
    persis sebelum perbaikan itu."""
    handler = _find_game_callback_handler()
    private_callback = _make_callback_query(ChatType.PRIVATE)

    matched, _ = await handler.check(private_callback)
    assert matched is True


async def test_game_callback_still_reachable_from_group_chat():
    handler = _find_game_callback_handler()
    group_callback = _make_callback_query(ChatType.GROUP)

    matched, _ = await handler.check(group_callback)
    assert matched is True
