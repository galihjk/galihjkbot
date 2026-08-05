from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ACTIVE_GAME_STATUSES, GamePlayerStatus
from app.database.models.game_event import GameEvent
from app.database.models.game_player import GamePlayer
from app.database.models.game_session import GameSession
from app.database.models.user_game_score import UserGameScore
from app.utils.datetime import utcnow

_ACTIVE_PLAYER_STATUSES = {GamePlayerStatus.JOINED.value, GamePlayerStatus.ACTIVE.value}


async def create_session(
    session: AsyncSession,
    *,
    group_id: int,
    game_key: str,
    created_by_user_id: int,
    min_players: int,
    max_players: int,
) -> GameSession:
    game_session = GameSession(
        group_id=group_id,
        game_key=game_key,
        created_by_user_id=created_by_user_id,
        min_players=min_players,
        max_players=max_players,
        state_json={},
    )
    session.add(game_session)
    await session.flush()
    return game_session


async def find_active_by_group(
    session: AsyncSession, group_id: int
) -> GameSession | None:
    result = await session.execute(
        select(GameSession).where(
            GameSession.group_id == group_id,
            GameSession.status.in_([s.value for s in ACTIVE_GAME_STATUSES]),
        )
    )
    return result.scalar_one_or_none()


async def find_by_id(session: AsyncSession, session_id: int) -> GameSession | None:
    result = await session.execute(
        select(GameSession).where(GameSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def find_all_active(session: AsyncSession) -> list[GameSession]:
    result = await session.execute(
        select(GameSession).where(
            GameSession.status.in_([s.value for s in ACTIVE_GAME_STATUSES])
        )
    )
    return list(result.scalars().all())


async def add_player(
    session: AsyncSession, game_session_id: int, user_id: int
) -> GamePlayer:
    player = GamePlayer(
        game_session_id=game_session_id,
        user_id=user_id,
        joined_at=utcnow(),
    )
    session.add(player)
    await session.flush()
    return player


async def find_player(
    session: AsyncSession, game_session_id: int, user_id: int
) -> GamePlayer | None:
    result = await session.execute(
        select(GamePlayer).where(
            GamePlayer.game_session_id == game_session_id,
            GamePlayer.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def find_active_players(
    session: AsyncSession, game_session_id: int
) -> list[GamePlayer]:
    result = await session.execute(
        select(GamePlayer).where(
            GamePlayer.game_session_id == game_session_id,
            GamePlayer.status.in_(_ACTIVE_PLAYER_STATUSES),
        )
    )
    return list(result.scalars().all())


async def count_active_players(session: AsyncSession, game_session_id: int) -> int:
    return len(await find_active_players(session, game_session_id))


async def find_all_players(session: AsyncSession, game_session_id: int) -> list[GamePlayer]:
    """Semua pemain yang pernah tercatat di sesi ini, status apa pun (WINNER,
    ELIMINATED, AFK, LEFT, dst) -- dipakai untuk hitung skor akhir sesi."""
    result = await session.execute(
        select(GamePlayer).where(GamePlayer.game_session_id == game_session_id)
    )
    return list(result.scalars().all())


async def commit_scores(
    session: AsyncSession,
    *,
    game_key: str,
    session_id: int,
    breakdown: dict,
) -> bool:
    """Commit skor akhir tiap pemain, idempoten per `session_id` -- skip diam-diam
    (return False, tidak insert apa pun) kalau sesi ini sudah pernah commit
    sebelumnya (lihat game-development-guide.md §15). `breakdown` bebas
    berupa objek apa pun asal punya atribut result_score/participation_score/
    survival_score/final_score (lihat ScoreBreakdown di engine/score.py)."""
    existing = await session.execute(
        select(UserGameScore.id).where(UserGameScore.session_id == session_id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return False

    now = utcnow()
    for user_id, score in breakdown.items():
        session.add(
            UserGameScore(
                user_id=user_id,
                game_key=game_key,
                session_id=session_id,
                result_score=score.result_score,
                participation_score=score.participation_score,
                survival_score=score.survival_score,
                final_score=score.final_score,
                committed_at=now,
            )
        )
    await session.flush()
    return True


async def log_event(
    session: AsyncSession,
    game_session_id: int,
    event_type: str,
    actor_user_id: int | None = None,
    payload: dict | None = None,
) -> GameEvent:
    event = GameEvent(
        game_session_id=game_session_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        payload_json=payload,
    )
    session.add(event)
    await session.flush()
    return event
