from __future__ import annotations

from aiogram.enums import ChatMemberStatus

from app.modules.leaderboard import period
from app.modules.leaderboard.handlers import handle_leaderboard, handle_skor
from tests.modules.leaderboard.conftest import make_group, make_settings, make_user, seed_score


class RecordingMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


async def test_skor_shows_not_subscribed_notice_with_link(session_factory, leaderboard_bot):
    settings = make_settings()
    async with session_factory() as db:
        user = await make_user(db, 1)
        await db.commit()
    leaderboard_bot.set_member_status(user.telegram_user_id, ChatMemberStatus.LEFT)

    async with session_factory() as db:
        current_user = await db.get(type(user), user.id)
        message = RecordingMessage()
        await handle_skor(message, leaderboard_bot, db, current_user, settings)
        await db.commit()

    assert len(message.answers) == 1
    text = message.answers[0]
    assert "belum subscribe" in text
    assert settings.telegram_leaderboard_channel_link in text

    async with session_factory() as db:
        refreshed = await db.get(type(user), user.id)
        assert refreshed.is_leaderboard_channel_subscribed is False


async def test_skor_shows_subscribed_notice(session_factory, leaderboard_bot):
    settings = make_settings()
    async with session_factory() as db:
        user = await make_user(db, 1)
        await db.commit()
    leaderboard_bot.set_member_status(user.telegram_user_id, ChatMemberStatus.MEMBER)

    async with session_factory() as db:
        current_user = await db.get(type(user), user.id)
        message = RecordingMessage()
        await handle_skor(message, leaderboard_bot, db, current_user, settings)
        await db.commit()

    text = message.answers[0]
    assert "sudah subscribe" in text

    async with session_factory() as db:
        refreshed = await db.get(type(user), user.id)
        assert refreshed.is_leaderboard_channel_subscribed is True


async def test_skor_falls_back_to_cached_status_on_check_error(session_factory, leaderboard_bot):
    settings = make_settings()
    async with session_factory() as db:
        user = await make_user(db, 1)
        user.is_leaderboard_channel_subscribed = True
        await db.commit()
    leaderboard_bot.set_member_error(user.telegram_user_id, RuntimeError("simulated"))

    async with session_factory() as db:
        current_user = await db.get(type(user), user.id)
        message = RecordingMessage()
        await handle_skor(message, leaderboard_bot, db, current_user, settings)
        await db.commit()

    text = message.answers[0]
    assert "sudah subscribe" in text  # pakai cache lama, tidak crash

    async with session_factory() as db:
        refreshed = await db.get(type(user), user.id)
        assert refreshed.is_leaderboard_channel_subscribed is True  # tidak ditimpa


async def test_skor_skips_notice_when_channel_not_configured(session_factory, leaderboard_bot):
    settings = make_settings(telegram_leaderboard_channel_id=None)
    async with session_factory() as db:
        user = await make_user(db, 1)
        await db.commit()

    async with session_factory() as db:
        current_user = await db.get(type(user), user.id)
        message = RecordingMessage()
        await handle_skor(message, leaderboard_bot, db, current_user, settings)

    text = message.answers[0]
    assert "subscribe" not in text.lower()
    assert leaderboard_bot.get_chat_member_calls == []


async def test_leaderboard_command_only_lists_subscribed_users(session_factory, leaderboard_bot):
    settings = make_settings()
    start, _end, _label = period.previous_period_window(settings.timezone)
    async with session_factory() as db:
        group_id = await make_group(db)
        subscribed = await make_user(db, 1)
        unsubscribed = await make_user(db, 2)
        subscribed.is_leaderboard_channel_subscribed = True
        current_start, _, _ = period.current_period_window(settings.timezone)
        await seed_score(
            db, user_id=subscribed.id, group_id=group_id, final_score=10, committed_at=current_start
        )
        await seed_score(
            db, user_id=unsubscribed.id, group_id=group_id, final_score=99, committed_at=current_start
        )
        await db.commit()

        message = RecordingMessage()
        await handle_leaderboard(message, db, settings)

    text = "\n".join(message.answers)
    assert "Virtual Player 1" in text
    assert "Virtual Player 2" not in text
