from __future__ import annotations

import asyncio
import hashlib

from app.database.repositories import autoreply_repository
from app.modules.autoreply.cache import AutoreplyRuleCache
from app.modules.autoreply.exceptions import AutoreplySyncInProgressError
from app.modules.autoreply.schemas import RawSource
from app.modules.autoreply.sync_service import AutoreplySyncService

HEADER = "Command,Message,MatchAll,ReplyToSender,ReplyToReplied,AdminOnly,Disabled"


def _csv(*rows: str) -> bytes:
    return ("\n".join([HEADER, *rows])).encode("utf-8")


class FakeRuleSource:
    def __init__(self, content: bytes, *, delay: float = 0.0) -> None:
        self.content = content
        self.delay = delay
        self.call_count = 0

    async def fetch(self) -> RawSource:
        self.call_count += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return RawSource(
            content=self.content,
            checksum=hashlib.sha256(self.content).hexdigest(),
            etag=None,
            last_modified=None,
            http_status=200,
        )


def _make_service(content: bytes, *, keep_snapshots: int = 3, delay: float = 0.0):
    source = FakeRuleSource(content, delay=delay)
    cache = AutoreplyRuleCache()
    service = AutoreplySyncService(
        source,
        cache,
        source_url="https://example.com/sheet.csv",
        keep_snapshots=keep_snapshots,
    )
    return service, cache, source


VALID_CSV = _csv('halo,"Halo, (sbj_dpn)!",TRUE,TRUE,FALSE,FALSE,FALSE')
VALID_CSV_V2 = _csv(
    'halo,"Halo lagi, (sbj_dpn)!",TRUE,TRUE,FALSE,FALSE,FALSE',
    'peluk,"(sbj_dpn) peluk semua",FALSE,FALSE,FALSE,FALSE,FALSE',
)
INVALID_CSV_MISSING_HEADER = b"Command,Message\nhalo,hai"
INVALID_CSV_BAD_ROW = _csv(",hai,TRUE,FALSE,FALSE,FALSE,FALSE")


async def test_first_sync_activates_snapshot_and_populates_cache(session_factory):
    service, cache, source = _make_service(VALID_CSV)
    async with session_factory() as db_session:
        result = await service.sync(
            db_session, triggered_by_user_id=None, reason="manual"
        )

    assert result.status == "success"
    assert result.active_rows == 1
    snapshot = cache.get()
    assert snapshot.is_empty is False
    assert len(snapshot.rules) == 1
    assert snapshot.rules[0].command == "halo"


async def test_second_sync_same_checksum_is_unchanged(session_factory):
    service, cache, source = _make_service(VALID_CSV)
    async with session_factory() as db_session:
        await service.sync(db_session, triggered_by_user_id=None, reason="manual")

    async with session_factory() as db_session:
        result = await service.sync(
            db_session, triggered_by_user_id=None, reason="manual"
        )
        active_sets = await autoreply_repository.find_active_rule_set(db_session)

    assert result.status == "unchanged"
    assert active_sets is not None
    # Cache tidak berubah -- masih snapshot dari sync pertama.
    assert len(cache.get().rules) == 1


async def test_third_sync_with_new_content_supersedes_previous(session_factory):
    service, cache, source = _make_service(VALID_CSV)
    async with session_factory() as db_session:
        first = await service.sync(
            db_session, triggered_by_user_id=None, reason="manual"
        )

    source.content = VALID_CSV_V2
    async with session_factory() as db_session:
        second = await service.sync(
            db_session, triggered_by_user_id=None, reason="manual"
        )

    assert second.status == "success"
    assert second.public_id != first.public_id
    assert len(cache.get().rules) == 2

    async with session_factory() as db_session:
        active = await autoreply_repository.find_active_rule_set(db_session)
        assert active.public_id == second.public_id


async def test_sync_with_missing_header_fails_and_keeps_last_known_good(session_factory):
    service, cache, source = _make_service(VALID_CSV)
    async with session_factory() as db_session:
        await service.sync(db_session, triggered_by_user_id=None, reason="manual")

    source.content = INVALID_CSV_MISSING_HEADER
    async with session_factory() as db_session:
        result = await service.sync(
            db_session, triggered_by_user_id=None, reason="manual"
        )

    assert result.status == "failed"
    assert result.error_reference is not None
    # Snapshot lama tetap dipakai (last-known-good).
    assert len(cache.get().rules) == 1
    assert cache.get().rules[0].command == "halo"


async def test_sync_with_one_bad_row_rejects_entire_snapshot(session_factory):
    service, cache, source = _make_service(VALID_CSV)
    async with session_factory() as db_session:
        await service.sync(db_session, triggered_by_user_id=None, reason="manual")

    source.content = INVALID_CSV_BAD_ROW
    async with session_factory() as db_session:
        result = await service.sync(
            db_session, triggered_by_user_id=None, reason="manual"
        )

    assert result.status == "failed"
    assert len(cache.get().rules) == 1


async def test_concurrent_sync_second_call_rejected(session_factory):
    service, cache, source = _make_service(VALID_CSV, delay=0.2)

    async def _run() -> object:
        async with session_factory() as db_session:
            return await service.sync(
                db_session, triggered_by_user_id=None, reason="manual"
            )

    async def _run_second_soon() -> object:
        await asyncio.sleep(0.02)
        async with session_factory() as db_session:
            try:
                return await service.sync(
                    db_session, triggered_by_user_id=None, reason="manual"
                )
            except AutoreplySyncInProgressError as exc:
                return exc

    first_result, second_result = await asyncio.gather(_run(), _run_second_soon())
    assert first_result.status == "success"
    assert isinstance(second_result, AutoreplySyncInProgressError)


async def test_retention_deletes_old_superseded_snapshots(session_factory):
    service, cache, source = _make_service(VALID_CSV, keep_snapshots=2)

    contents = [
        _csv(f'halo{i},"versi {i}",TRUE,FALSE,FALSE,FALSE,FALSE') for i in range(4)
    ]
    for content in contents:
        source.content = content
        async with session_factory() as db_session:
            await service.sync(db_session, triggered_by_user_id=None, reason="manual")

    async with session_factory() as db_session:
        from sqlalchemy import select

        from app.database.models.autoreply_rule_set import AutoreplyRuleSet

        result = await db_session.execute(select(AutoreplyRuleSet))
        remaining = list(result.scalars().all())

    # keep_snapshots=2 -> 1 active + 1 superseded dipertahankan, sisanya dihapus.
    assert len(remaining) == 2
    statuses = sorted(rule_set.status for rule_set in remaining)
    assert statuses == ["active", "superseded"]


async def test_load_active_snapshot_returns_none_when_empty(session_factory):
    service, cache, source = _make_service(VALID_CSV)
    async with session_factory() as db_session:
        info = await service.load_active_snapshot(db_session)
    assert info is None
    assert cache.get().is_empty


async def test_load_active_snapshot_restores_cache_after_restart(session_factory):
    service, cache, source = _make_service(VALID_CSV)
    async with session_factory() as db_session:
        await service.sync(db_session, triggered_by_user_id=None, reason="manual")

    # Simulasikan restart: cache baru yang kosong, service baru yang
    # menunjuk ke database yang sama.
    fresh_cache = AutoreplyRuleCache()
    fresh_service = AutoreplySyncService(
        source,
        fresh_cache,
        source_url="https://example.com/sheet.csv",
        keep_snapshots=3,
    )
    async with session_factory() as db_session:
        info = await fresh_service.load_active_snapshot(db_session)

    assert info is not None
    assert info.status == "active"
    assert len(fresh_cache.get().rules) == 1
