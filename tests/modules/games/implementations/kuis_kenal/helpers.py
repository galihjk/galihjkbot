from __future__ import annotations

from app.database.repositories.game_repository import find_by_id
from tests.conftest import FakeCallback, FakeMessage


def extract_start_payload(markup) -> str | None:
    """Cari button URL '?start=<payload>' di sebuah InlineKeyboardMarkup --
    dipakai test untuk mensimulasikan klik deep link (yang sesungguhnya
    membuka /start baru di client Telegram, bukan callback)."""
    if markup is None:
        return None
    for row in markup.inline_keyboard:
        for button in row:
            url = getattr(button, "url", None)
            if url and "?start=" in url:
                return url.split("?start=", 1)[1]
    return None


def latest_markup_to(bot, chat_id):
    """Reply markup PALING BARU (dari send_message ATAU edit) yang ditujukan
    ke `chat_id` tertentu -- baik grup maupun private chat seorang user."""
    events = []
    for m in bot.sent:
        if m.chat.id == chat_id and m.reply_markup is not None:
            events.append(m.reply_markup)
    for e in bot.edits:
        if e["chat_id"] == chat_id and e.get("reply_markup") is not None:
            events.append(e["reply_markup"])
    return events[-1] if events else None


async def open_deep_link(game, game_world, session_id, payload, *, user_id, chat_id):
    incoming = FakeMessage(game_world.bot, chat_id)
    async with game_world.session_factory() as db_session:
        await game.handle_deep_link(
            payload, message=incoming, db_session=db_session,
            acting_user_id=user_id, game_manager=game_world.manager,
        )
    return incoming


async def send_callback(game_world, session_id, data, *, message_id, chat_id, user_id):
    callback = FakeCallback(session_id, data, message_id=message_id, chat_id=chat_id)
    async with game_world.session_factory() as db_session:
        await game_world.manager.handle_callback(
            db_session, session_id=session_id, callback=callback, acting_user_id=user_id
        )
    return callback


async def send_private_text(game_world, session_id, text, *, user_id, chat_id):
    message = FakeMessage(game_world.bot, chat_id, text=text)
    async with game_world.session_factory() as db_session:
        await game_world.manager.handle_message(
            db_session, session_id=session_id, message=message, acting_user_id=user_id
        )
    return message


async def fire_round_timeout(game, game_world, session_id):
    """Picu timer "round" langsung (tanpa benar-benar menunggu delay
    aslinya) -- pola yang sama dipakai test Kursi Kosong: bangun context
    lewat `GameManager._build_context` lalu panggil `handle_timeout`
    langsung."""
    async with game_world.session_factory() as db_session:
        game_session = await find_by_id(db_session, session_id)
        context = await game_world.manager._build_context(db_session, game_session)
        await game.handle_timeout(context, f"turn:{session_id}:round")
        await db_session.commit()
