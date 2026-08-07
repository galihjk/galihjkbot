from __future__ import annotations

from app.database.repositories import leaderboard_repository
from app.utils.datetime import utcnow
from tests.modules.leaderboard.conftest import make_group, make_user, seed_score


async def test_sum_global_scores_by_user_subscribed_excludes_unsubscribed(session_factory):
    start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(month=start.month + 1) if start.month < 12 else start.replace(
        year=start.year + 1, month=1
    )

    async with session_factory() as db:
        group_id = await make_group(db)
        subscribed_user = await make_user(db, 1)
        unsubscribed_user = await make_user(db, 2)
        subscribed_user.is_leaderboard_channel_subscribed = True
        unsubscribed_user.is_leaderboard_channel_subscribed = False
        await seed_score(
            db,
            user_id=subscribed_user.id,
            group_id=group_id,
            final_score=10,
            committed_at=start,
        )
        await seed_score(
            db,
            user_id=unsubscribed_user.id,
            group_id=group_id,
            final_score=99,
            committed_at=start,
        )
        await db.commit()

    async with session_factory() as db:
        rows = await leaderboard_repository.sum_global_scores_by_user_subscribed(
            db, start, end
        )

    assert [user.id for user, _ in rows] == [subscribed_user.id]
    assert rows[0][1] == 10


async def test_sum_global_scores_by_user_raw_includes_everyone(session_factory):
    start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(month=start.month + 1) if start.month < 12 else start.replace(
        year=start.year + 1, month=1
    )

    async with session_factory() as db:
        group_id = await make_group(db)
        subscribed_user = await make_user(db, 1)
        unsubscribed_user = await make_user(db, 2)
        subscribed_user.is_leaderboard_channel_subscribed = True
        await seed_score(
            db, user_id=subscribed_user.id, group_id=group_id, final_score=10, committed_at=start
        )
        await seed_score(
            db, user_id=unsubscribed_user.id, group_id=group_id, final_score=5, committed_at=start
        )
        await db.commit()

    async with session_factory() as db:
        rows = await leaderboard_repository.sum_global_scores_by_user(db, start, end)

    assert {user.id for user, _ in rows} == {subscribed_user.id, unsubscribed_user.id}


async def test_set_channel_subscription_updates_flag(session_factory):
    async with session_factory() as db:
        user = await make_user(db, 1)
        await db.commit()
        user_id = user.id
        assert user.is_leaderboard_channel_subscribed is False

    async with session_factory() as db:
        await leaderboard_repository.set_channel_subscription(db, user_id, True)
        await db.commit()

    async with session_factory() as db:
        from app.database.repositories import user_repository

        refreshed = await user_repository.find_by_id(db, user_id)
        assert refreshed.is_leaderboard_channel_subscribed is True
