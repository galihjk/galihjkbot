from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.autoreply_rule import AutoreplyRule
from app.database.models.autoreply_rule_set import AutoreplyRuleSet
from app.database.models.autoreply_sync_run import AutoreplySyncRun
from app.database.repositories import audit_repository, autoreply_repository
from app.modules.autoreply.cache import AutoreplyRuleCache
from app.modules.autoreply.constants import (
    SYNC_STATUS_FAILED,
    SYNC_STATUS_RUNNING,
    SYNC_STATUS_SUCCESS,
    SYNC_STATUS_UNCHANGED,
)
from app.modules.autoreply.exceptions import (
    AutoreplyCSVParseError,
    AutoreplyHeaderError,
    AutoreplySourceFetchError,
    AutoreplySourceTooLargeError,
    AutoreplySyncInProgressError,
)
from app.modules.autoreply.schemas import (
    AutoreplyCacheSnapshot,
    AutoreplySnapshotInfo,
    AutoreplySyncResult,
    CachedAutoreplyRule,
)
from app.modules.autoreply.sources.base import RuleSource
from app.modules.autoreply.validators import parse_and_validate
from app.utils.datetime import utcnow
from app.utils.errors import generate_error_reference

logger = logging.getLogger(__name__)

_MAX_REPORTED_ISSUES = 50


def _to_cached_rule(rule: AutoreplyRule) -> CachedAutoreplyRule:
    return CachedAutoreplyRule(
        id=rule.id,
        rule_set_id=rule.rule_set_id,
        source_row=rule.source_row,
        command=rule.command,
        normalized_command=rule.normalized_command,
        message_template=rule.message_template,
        response_type=rule.response_type,
        media_file_id=rule.media_file_id,
        match_all=rule.match_all,
        reply_to_sender=rule.reply_to_sender,
        reply_to_replied=rule.reply_to_replied,
        admin_only=rule.admin_only,
    )


def to_snapshot_info(rule_set: AutoreplyRuleSet) -> AutoreplySnapshotInfo:
    return AutoreplySnapshotInfo(
        rule_set_id=rule_set.id,
        public_id=rule_set.public_id or "",
        status=rule_set.status,
        total_rows=rule_set.total_rows,
        active_rows=rule_set.active_rows,
        disabled_rows=rule_set.disabled_rows,
        warning_count=rule_set.warning_count,
        source_checksum=rule_set.source_checksum,
        activated_at=rule_set.activated_at,
    )


class AutoreplySyncService:
    """Orkestrasi sinkronisasi (§13.6, §16). Satu instance dibagi lintas
    request (state: sync lock) -- dibuat sekali di bootstrap, sama seperti
    `AutoreplyRuleCache`."""

    def __init__(
        self,
        source: RuleSource,
        cache: AutoreplyRuleCache,
        *,
        source_url: str,
        keep_snapshots: int,
    ) -> None:
        self._source = source
        self._cache = cache
        self._source_url = source_url
        self._keep_snapshots = keep_snapshots
        self._sync_lock = asyncio.Lock()

    async def load_active_snapshot(
        self, session: AsyncSession
    ) -> AutoreplySnapshotInfo | None:
        """Dipanggil saat startup -- muat snapshot aktif dari SQLite ke
        cache TANPA menyentuh network (§16.3 langkah 2)."""
        rule_set = await autoreply_repository.find_active_rule_set(session)
        if rule_set is None:
            return None

        rules = await autoreply_repository.find_rules_by_rule_set_id(
            session, rule_set.id, only_enabled=True
        )
        snapshot = AutoreplyCacheSnapshot(
            rule_set_id=rule_set.id,
            public_id=rule_set.public_id,
            checksum=rule_set.source_checksum,
            activated_at=rule_set.activated_at,
            rules=tuple(_to_cached_rule(rule) for rule in rules),
        )
        await self._cache.replace(snapshot)
        return to_snapshot_info(rule_set)

    async def sync(
        self,
        session: AsyncSession,
        *,
        triggered_by_user_id: int | None,
        reason: str,
    ) -> AutoreplySyncResult:
        if self._sync_lock.locked():
            raise AutoreplySyncInProgressError(
                "Sinkronisasi lain sedang berjalan, coba lagi sebentar."
            )
        async with self._sync_lock:
            return await self._sync_locked(
                session, triggered_by_user_id=triggered_by_user_id, reason=reason
            )

    async def _sync_locked(
        self,
        session: AsyncSession,
        *,
        triggered_by_user_id: int | None,
        reason: str,
    ) -> AutoreplySyncResult:
        started_at = utcnow()
        sync_run = await autoreply_repository.insert_sync_run(
            session,
            reason=reason,
            triggered_by_user_id=triggered_by_user_id,
            source_url=self._source_url,
            status=SYNC_STATUS_RUNNING,
            started_at=started_at,
        )
        await session.commit()

        try:
            raw = await self._source.fetch()
        except (AutoreplySourceFetchError, AutoreplySourceTooLargeError) as exc:
            return await self._fail(session, sync_run, started_at, str(exc))

        active_rule_set = await autoreply_repository.find_active_rule_set(session)
        if active_rule_set is not None and active_rule_set.source_checksum == raw.checksum:
            await autoreply_repository.update_sync_run(
                session,
                sync_run,
                status=SYNC_STATUS_UNCHANGED,
                http_status=raw.http_status,
                source_checksum=raw.checksum,
                finished_at=utcnow(),
            )
            await session.commit()
            return AutoreplySyncResult(
                status=SYNC_STATUS_UNCHANGED,
                public_id=active_rule_set.public_id,
                total_rows=active_rule_set.total_rows,
                active_rows=active_rule_set.active_rows,
                disabled_rows=active_rule_set.disabled_rows,
            )

        try:
            document = parse_and_validate(raw.content)
        except (AutoreplyCSVParseError, AutoreplyHeaderError) as exc:
            return await self._fail(session, sync_run, started_at, str(exc))

        if not document.is_valid:
            messages = [issue.message for issue in document.errors][:_MAX_REPORTED_ISSUES]
            return await self._fail(
                session,
                sync_run,
                started_at,
                "; ".join(messages),
                error_count=len(document.errors),
                warning_count=len(document.warnings),
                row_errors=tuple(messages),
            )

        active_rows = sum(1 for row in document.rows if not row.disabled)
        disabled_rows = sum(1 for row in document.rows if row.disabled)

        rule_set = await autoreply_repository.insert_rule_set(
            session,
            source_url=self._source_url,
            source_checksum=raw.checksum,
            source_etag=raw.etag,
            source_last_modified=raw.last_modified,
            status="pending",
            total_rows=document.total_rows,
            active_rows=active_rows,
            disabled_rows=disabled_rows,
            warning_count=len(document.warnings),
            imported_by_user_id=triggered_by_user_id,
            imported_at=started_at,
        )
        rules = [
            AutoreplyRule(
                rule_set_id=rule_set.id,
                source_row=row.source_row,
                command=row.command,
                normalized_command=row.normalized_command,
                message_template=row.message_template,
                response_type=row.response_type,
                media_file_id=row.media_file_id,
                match_all=row.match_all,
                reply_to_sender=row.reply_to_sender,
                reply_to_replied=row.reply_to_replied,
                admin_only=row.admin_only,
                disabled=row.disabled,
                source_payload_json=row.source_payload,
            )
            for row in document.rows
        ]
        await autoreply_repository.insert_rules(session, rules)

        activated_at = utcnow()
        await autoreply_repository.activate_rule_set(session, rule_set, activated_at)
        await autoreply_repository.supersede_other_active(session, rule_set.id)
        await audit_repository.record(
            session,
            actor_user_id=triggered_by_user_id,
            action="autoreply.activate_snapshot",
            entity_type="autoreply_rule_set",
            entity_id=rule_set.public_id,
            old_value=active_rule_set.public_id if active_rule_set else None,
            new_value=rule_set.public_id,
        )
        await session.commit()

        cached_rules = tuple(
            _to_cached_rule(rule) for rule in rules if not rule.disabled
        )
        await self._cache.replace(
            AutoreplyCacheSnapshot(
                rule_set_id=rule_set.id,
                public_id=rule_set.public_id,
                checksum=rule_set.source_checksum,
                activated_at=activated_at,
                rules=cached_rules,
            )
        )

        await self._cleanup_old_snapshots(session)

        duration_ms = (utcnow() - started_at).total_seconds() * 1000
        await autoreply_repository.update_sync_run(
            session,
            sync_run,
            status=SYNC_STATUS_SUCCESS,
            http_status=raw.http_status,
            source_checksum=raw.checksum,
            total_rows=document.total_rows,
            active_rows=active_rows,
            disabled_rows=disabled_rows,
            warning_count=len(document.warnings),
            finished_at=utcnow(),
        )
        await session.commit()

        return AutoreplySyncResult(
            status=SYNC_STATUS_SUCCESS,
            public_id=rule_set.public_id,
            total_rows=document.total_rows,
            active_rows=active_rows,
            disabled_rows=disabled_rows,
            warning_count=len(document.warnings),
            duration_ms=duration_ms,
            row_warnings=tuple(
                issue.message for issue in document.warnings[:_MAX_REPORTED_ISSUES]
            ),
        )

    async def _cleanup_old_snapshots(self, session: AsyncSession) -> None:
        keep_superseded = max(self._keep_snapshots - 1, 0)
        stale_ids = await autoreply_repository.find_old_rule_set_ids_beyond_retention(
            session, keep_superseded=keep_superseded
        )
        if stale_ids:
            await autoreply_repository.delete_rule_sets_by_ids(session, stale_ids)
            await session.commit()

    async def _fail(
        self,
        session: AsyncSession,
        sync_run: AutoreplySyncRun,
        started_at: datetime,
        message: str,
        *,
        error_count: int = 1,
        warning_count: int = 0,
        row_errors: tuple[str, ...] = (),
    ) -> AutoreplySyncResult:
        reference = generate_error_reference()
        finished_at = utcnow()
        duration_ms = (finished_at - started_at).total_seconds() * 1000
        logger.warning(
            "Sinkronisasi autoreply gagal. reference=%s sync_run_id=%s",
            reference,
            sync_run.id,
        )
        await autoreply_repository.update_sync_run(
            session,
            sync_run,
            status=SYNC_STATUS_FAILED,
            error_count=error_count,
            warning_count=warning_count,
            error_reference=reference,
            summary_json={"errors": list(row_errors) or [message]},
            finished_at=finished_at,
        )
        await session.commit()
        return AutoreplySyncResult(
            status=SYNC_STATUS_FAILED,
            error_reference=reference,
            error_count=error_count,
            warning_count=warning_count,
            duration_ms=duration_ms,
            row_errors=row_errors or (message,),
        )
