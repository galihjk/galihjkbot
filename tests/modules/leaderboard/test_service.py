from __future__ import annotations

from aiogram.enums import ChatMemberStatus

from app.database.repositories import leaderboard_repository, user_repository
from app.modules.leaderboard import period
from app.modules.leaderboard.service import run_monthly_maintenance
from tests.modules.leaderboard.conftest import make_group, make_user, make_settings, seed_score


async def _seed_two_users(session_factory, settings):
    """Dua user berskor bulan LALU (window yang akan diproses job), belum
    ada cache subscribe apa pun -- dipakai hampir semua test di file ini."""
    start, _end, _label = period.previous_period_window(settings.timezone)
    async with session_factory() as db:
        group_id = await make_group(db)
        user_a = await make_user(db, 1)
        user_b = await make_user(db, 2)
        await seed_score(db, user_id=user_a.id, group_id=group_id, final_score=10, committed_at=start)
        await seed_score(db, user_id=user_b.id, group_id=group_id, final_score=20, committed_at=start)
        await db.commit()
        user_a_id, user_b_id = user_a.id, user_b.id
        user_a_tid, user_b_tid = user_a.telegram_user_id, user_b.telegram_user_id
    return group_id, (user_a_id, user_a_tid), (user_b_id, user_b_tid)


async def test_only_live_subscribed_users_posted_to_channel(
    session_factory, leaderboard_bot, maintenance_gate
):
    settings = make_settings()
    _group_id, (a_id, a_tid), (b_id, b_tid) = await _seed_two_users(session_factory, settings)
    leaderboard_bot.set_member_status(a_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.set_member_status(b_tid, ChatMemberStatus.LEFT)

    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    channel_texts = leaderboard_bot.texts_to(settings.telegram_leaderboard_channel_id)
    global_post = next(t for t in channel_texts if "LEADERBOARD GLOBAL" in t)
    assert "Virtual Player 1" in global_post
    assert "Virtual Player 2" not in global_post

    async with session_factory() as db:
        user_a = await user_repository.find_by_id(db, a_id)
        user_b = await user_repository.find_by_id(db, b_id)
    assert user_a.is_leaderboard_channel_subscribed is True
    assert user_b.is_leaderboard_channel_subscribed is False


async def test_failed_check_keeps_old_cache_and_excludes_from_this_cycle(
    session_factory, leaderboard_bot, maintenance_gate
):
    settings = make_settings()
    _group_id, (a_id, a_tid), (_b_id, b_tid) = await _seed_two_users(session_factory, settings)

    async with session_factory() as db:
        user_a = await user_repository.find_by_id(db, a_id)
        user_a.is_leaderboard_channel_subscribed = True
        await db.commit()

    leaderboard_bot.set_member_error(a_tid, RuntimeError("simulated get_chat_member failure"))
    leaderboard_bot.set_member_status(b_tid, ChatMemberStatus.MEMBER)

    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    channel_texts = leaderboard_bot.texts_to(settings.telegram_leaderboard_channel_id)
    global_post = next(t for t in channel_texts if "LEADERBOARD GLOBAL" in t)
    assert "Virtual Player 1" not in global_post

    async with session_factory() as db:
        refreshed = await user_repository.find_by_id(db, a_id)
    assert refreshed.is_leaderboard_channel_subscribed is True


async def test_channel_post_failure_cancels_whole_job(
    session_factory, leaderboard_bot, maintenance_gate
):
    settings = make_settings()
    start, end, _label = period.previous_period_window(settings.timezone)
    _group_id, (_a_id, a_tid), (_b_id, b_tid) = await _seed_two_users(session_factory, settings)
    leaderboard_bot.set_member_status(a_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.set_member_status(b_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.fail_send_to.add(settings.telegram_leaderboard_channel_id)

    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    async with session_factory() as db:
        rows = await leaderboard_repository.sum_global_scores_by_user(db, start, end)
        has_run = await leaderboard_repository.has_run(db, _label)
    assert len(rows) == 2  # skor TIDAK dihapus
    assert has_run is False  # job akan dicoba lagi siklus berikutnya
    assert maintenance_gate.active is False


async def test_per_group_post_failure_does_not_cancel_job(session_factory, leaderboard_bot, maintenance_gate):
    settings = make_settings()
    start, end, label = period.previous_period_window(settings.timezone)
    async with session_factory() as db:
        group_a = await make_group(db, title="Grup A")
        group_b = await make_group(db, title="Grup B")
        user_a = await make_user(db, 1)
        user_b = await make_user(db, 2)
        await seed_score(db, user_id=user_a.id, group_id=group_a, final_score=10, committed_at=start)
        await seed_score(db, user_id=user_b.id, group_id=group_b, final_score=20, committed_at=start)
        await db.commit()
        user_a_tid, user_b_tid = user_a.telegram_user_id, user_b.telegram_user_id

    from app.database.repositories.group_repository import find_by_id as find_group_by_id

    async with session_factory() as db:
        group_b_row = await find_group_by_id(db, group_b)
        group_b_chat_id = group_b_row.telegram_chat_id

    leaderboard_bot.set_member_status(user_a_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.set_member_status(user_b_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.fail_send_to.add(group_b_chat_id)

    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    async with session_factory() as db:
        rows = await leaderboard_repository.sum_global_scores_by_user(db, start, end)
        has_run = await leaderboard_repository.has_run(db, label)
    assert rows == []  # job tetap lanjut sampai reset walau 1 grup gagal
    assert has_run is True


async def test_group_leaderboard_and_deletion_unaffected_by_subscription(
    session_factory, leaderboard_bot, maintenance_gate
):
    settings = make_settings()
    start, end, label = period.previous_period_window(settings.timezone)
    group_id, (a_id, a_tid), (b_id, b_tid) = await _seed_two_users(session_factory, settings)

    from app.database.repositories.group_repository import find_by_id as find_group_by_id

    async with session_factory() as db:
        group_row = await find_group_by_id(db, group_id)
        group_chat_id = group_row.telegram_chat_id

    leaderboard_bot.set_member_status(a_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.set_member_status(b_tid, ChatMemberStatus.LEFT)

    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    group_texts = leaderboard_bot.texts_to(group_chat_id)
    group_post = next(t for t in group_texts if "Virtual Player" in t)
    assert "Virtual Player 1" in group_post
    assert "Virtual Player 2" in group_post  # leaderboard grup TIDAK digating subscribe

    async with session_factory() as db:
        rows = await leaderboard_repository.sum_global_scores_by_user(db, start, end)
        has_run = await leaderboard_repository.has_run(db, label)
    assert rows == []  # skor SEMUA user tetap direset, terlepas status subscribe
    assert has_run is True


async def test_gate_released_after_success(session_factory, leaderboard_bot, maintenance_gate):
    settings = make_settings()
    _group_id, (_a_id, a_tid), (_b_id, b_tid) = await _seed_two_users(session_factory, settings)
    leaderboard_bot.set_member_status(a_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.set_member_status(b_tid, ChatMemberStatus.MEMBER)

    assert maintenance_gate.active is False
    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)
    assert maintenance_gate.active is False


async def test_gate_released_even_on_unexpected_exception(
    session_factory, leaderboard_bot, maintenance_gate, monkeypatch
):
    settings = make_settings()
    _group_id, (_a_id, a_tid), (_b_id, b_tid) = await _seed_two_users(session_factory, settings)
    leaderboard_bot.set_member_status(a_tid, ChatMemberStatus.MEMBER)
    leaderboard_bot.set_member_status(b_tid, ChatMemberStatus.MEMBER)

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated unexpected failure deep in the job")

    monkeypatch.setattr(leaderboard_repository, "delete_scores_in_range", _boom)

    import pytest

    with pytest.raises(RuntimeError):
        await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    assert maintenance_gate.active is False


async def test_channel_not_configured_skips_entirely(session_factory, leaderboard_bot, maintenance_gate):
    settings = make_settings(telegram_leaderboard_channel_id=None)
    await _seed_two_users(session_factory, settings)

    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    assert leaderboard_bot.sent == []
    assert leaderboard_bot.get_chat_member_calls == []
    assert maintenance_gate.active is False


async def test_already_ran_this_period_skips(session_factory, leaderboard_bot, maintenance_gate):
    settings = make_settings()
    _group_id, (_a_id, a_tid), (_b_id, b_tid) = await _seed_two_users(session_factory, settings)
    _start, _end, label = period.previous_period_window(settings.timezone)

    async with session_factory() as db:
        await leaderboard_repository.mark_run(db, label, _start)
        await db.commit()

    await run_monthly_maintenance(leaderboard_bot, session_factory, settings, maintenance_gate)

    assert leaderboard_bot.sent == []
    assert leaderboard_bot.get_chat_member_calls == []
    assert maintenance_gate.active is False
