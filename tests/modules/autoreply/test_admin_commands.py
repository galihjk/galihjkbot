from __future__ import annotations

import hashlib
from types import SimpleNamespace

from aiogram.filters import CommandObject

from app.database.repositories import audit_repository, user_repository
from app.modules.autoreply import admin_handlers
from app.modules.autoreply.cache import AutoreplyRuleCache
from app.modules.autoreply.exceptions import AutoreplySyncInProgressError
from app.modules.autoreply.schemas import RawSource
from app.modules.autoreply.sync_service import AutoreplySyncService
from app.modules.autoreply.texts import (
    FEATURE_DISABLED_GLOBAL,
    FEATURE_ENABLED_GLOBAL,
    FORMAT_HELP_TEXT,
    GROUP_COMMAND_USAGE,
    GROUP_NOT_FOUND,
    NO_SYNC_YET,
)


class RecordingMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, reply_markup=None, **kwargs) -> "RecordingMessage":
        self.answers.append(text)
        return self


class FakeRuleSource:
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def fetch(self) -> RawSource:
        return RawSource(
            content=self.content,
            checksum=hashlib.sha256(self.content).hexdigest(),
            etag=None,
            last_modified=None,
            http_status=200,
        )


HEADER = "Command,Message,MatchAll,ReplyToSender,ReplyToReplied,AdminOnly,Disabled"


def _csv(*rows: str) -> bytes:
    return ("\n".join([HEADER, *rows])).encode("utf-8")


def _sync_service(content: bytes) -> AutoreplySyncService:
    return AutoreplySyncService(
        FakeRuleSource(content),
        AutoreplyRuleCache(),
        source_url="https://example.com/sheet.csv",
        keep_snapshots=3,
    )


async def _make_user(session_factory):
    async with session_factory() as db_session:
        user = await user_repository.get_or_create_virtual_player(db_session, 0)
        await db_session.commit()
        return user.id, user


async def test_panel_shows_no_snapshot_when_empty(session_factory):
    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_panel(message, db_session)
    assert "Belum ada snapshot" in message.answers[0]


async def test_enable_and_disable_toggle_feature_and_audit(session_factory):
    user_id, user = await _make_user(session_factory)

    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_enable(message, db_session, user)
        await db_session.commit()
    assert message.answers == [FEATURE_ENABLED_GLOBAL]

    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_disable(message, db_session, user)
        await db_session.commit()
    assert message.answers == [FEATURE_DISABLED_GLOBAL]


async def test_group_toggle_usage_error(session_factory):
    _, user = await _make_user(session_factory)
    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_group_toggle(
            message, db_session, user, CommandObject(command="msgcmd_group", args="bad")
        )
    assert message.answers == [GROUP_COMMAND_USAGE]


async def test_group_toggle_not_found(session_factory):
    _, user = await _make_user(session_factory)
    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_group_toggle(
            message,
            db_session,
            user,
            CommandObject(command="msgcmd_group", args="-100123 on"),
        )
    assert message.answers == [GROUP_NOT_FOUND]


async def test_group_toggle_success(session_factory):
    from app.database.repositories import group_repository

    _, user = await _make_user(session_factory)
    async with session_factory() as db_session:
        group = await group_repository.upsert_group(
            db_session,
            SimpleNamespace(id=-100123, title="G", username=None, type="group"),
        )
        await db_session.commit()

    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_group_toggle(
            message,
            db_session,
            user,
            CommandObject(command="msgcmd_group", args="-100123 on"),
        )
        await db_session.commit()
    assert "diaktifkan untuk grup -100123" in message.answers[0]


async def test_format_help_returns_static_text():
    message = RecordingMessage()
    await admin_handlers.handle_format_help(message)
    assert message.answers == [FORMAT_HELP_TEXT]


async def test_sync_errors_before_any_sync(session_factory):
    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_sync_errors(message, db_session)
    assert message.answers == [NO_SYNC_YET]


async def test_reload_success_then_failure_reported(session_factory):
    user_id, user = await _make_user(session_factory)
    sync_service = _sync_service(
        _csv('halo,"Halo, (sbj_dpn)!",TRUE,TRUE,FALSE,FALSE,FALSE')
    )

    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_reload(message, db_session, user, sync_service)
    assert "BERHASIL DIMUAT" in message.answers[0]

    sync_service._source.content = b"Command,Message\nhalo,hai"
    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_reload(message, db_session, user, sync_service)
    assert "GAGAL DIMUAT" in message.answers[0]

    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_sync_errors(message, db_session)
    assert "Gagal" in message.answers[0]


async def test_reload_reports_in_progress_error(session_factory, monkeypatch):
    user_id, user = await _make_user(session_factory)
    sync_service = _sync_service(
        _csv('halo,"Halo!",TRUE,TRUE,FALSE,FALSE,FALSE')
    )

    async def _raise_in_progress(*args, **kwargs):
        raise AutoreplySyncInProgressError("Sinkronisasi lain sedang berjalan.")

    monkeypatch.setattr(sync_service, "sync", _raise_in_progress)

    message = RecordingMessage()
    async with session_factory() as db_session:
        await admin_handlers.handle_reload(message, db_session, user, sync_service)
    assert message.answers == ["Sinkronisasi lain sedang berjalan."]
