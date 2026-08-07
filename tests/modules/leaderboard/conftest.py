from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from aiogram.enums import ChatMemberStatus
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.maintenance import MaintenanceGate
from app.database.models.game_session import GameSession
from app.database.models.user_game_score import UserGameScore
from app.database.repositories import group_repository, user_repository


def make_settings(**overrides) -> Settings:
    defaults = dict(
        app_name="TestBot",
        app_env="development",
        app_version="0.0.0",
        timezone="Asia/Jakarta",
        telegram_bot_token="test-token",
        telegram_superadmin_ids=[],
        telegram_drop_pending_updates=False,
        telegram_leaderboard_channel_id=-100123456789,
        telegram_leaderboard_channel_link="https://t.me/testchannel",
        database_url=URL.create(drivername="sqlite+aiosqlite", database=":memory:"),
        log_level="INFO",
        autoreply_source_url="",
        autoreply_startup_sync=False,
        autoreply_sync_interval_seconds=0,
        autoreply_http_connect_timeout_seconds=5.0,
        autoreply_http_read_timeout_seconds=15.0,
        autoreply_max_source_bytes=5_242_880,
        autoreply_max_responses_per_message=20,
        autoreply_keep_snapshots=3,
        autoreply_allow_private=False,
        autoreply_ignore_bots=True,
    )
    defaults.update(overrides)
    return Settings(**defaults)


class FakeLeaderboardBot:
    """Bot tiruan khusus test leaderboard: `send_message` cuma mencatat
    riwayat (pola sama seperti `FakeBot` di `tests/conftest.py`), plus
    `get_chat_member` yang hasilnya diatur per `telegram_user_id` lewat
    `set_member_status`/`set_member_error` -- dipakai mensimulasikan re-cek
    subscribe channel."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.fail_send_to: set[int] = set()
        self._statuses: dict[int, ChatMemberStatus] = {}
        self._errors: dict[int, Exception] = {}
        self.get_chat_member_calls: list[tuple[int, int]] = []

    def set_member_status(self, telegram_user_id: int, status: ChatMemberStatus) -> None:
        self._statuses[telegram_user_id] = status
        self._errors.pop(telegram_user_id, None)

    def set_member_error(self, telegram_user_id: int, error: Exception) -> None:
        self._errors[telegram_user_id] = error
        self._statuses.pop(telegram_user_id, None)

    async def send_message(self, chat_id, text, **kwargs) -> SimpleNamespace:
        if chat_id in self.fail_send_to:
            raise RuntimeError(f"simulated send failure to chat {chat_id}")
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=len(self.sent))

    async def get_chat_member(self, chat_id, user_id) -> SimpleNamespace:
        self.get_chat_member_calls.append((chat_id, user_id))
        if user_id in self._errors:
            raise self._errors[user_id]
        status = self._statuses.get(user_id, ChatMemberStatus.LEFT)
        return SimpleNamespace(status=status)

    def texts_to(self, chat_id) -> list[str]:
        return [text for cid, text in self.sent if cid == chat_id]


@pytest.fixture
def leaderboard_bot() -> FakeLeaderboardBot:
    return FakeLeaderboardBot()


@pytest.fixture
def maintenance_gate() -> MaintenanceGate:
    return MaintenanceGate()


async def make_group(db_session: AsyncSession, *, title: str = "Test Group") -> int:
    chat_id = 1_000_000 + uuid.uuid4().int % 1_000_000
    group = await group_repository.upsert_group(
        db_session, SimpleNamespace(id=chat_id, title=title, username=None, type="group")
    )
    return group.id


async def seed_score(
    db_session: AsyncSession,
    *,
    user_id: int,
    group_id: int,
    final_score: int,
    committed_at: datetime,
    game_key: str = "test_game",
) -> None:
    """Bikin satu `GameSession` + satu `UserGameScore` sekali jalan --
    detail skor per-kategori (result/participation/survival) tidak relevan
    utk test leaderboard, jadi disamakan dengan `final_score`."""
    game_session = GameSession(
        group_id=group_id,
        game_key=game_key,
        min_players=1,
        max_players=8,
    )
    db_session.add(game_session)
    await db_session.flush()
    db_session.add(
        UserGameScore(
            user_id=user_id,
            game_key=game_key,
            session_id=game_session.id,
            result_score=final_score,
            participation_score=0,
            survival_score=0,
            final_score=final_score,
            committed_at=committed_at,
        )
    )
    await db_session.flush()


async def make_user(db_session: AsyncSession, index: int):
    return await user_repository.get_or_create_virtual_player(db_session, index)
