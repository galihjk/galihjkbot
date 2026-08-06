from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.autoreply_rule import AutoreplyRule
from app.database.models.autoreply_rule_set import AutoreplyRuleSet
from app.database.models.autoreply_sync_run import AutoreplySyncRun


async def insert_rule_set(
    session: AsyncSession,
    *,
    source_url: str,
    source_checksum: str,
    source_etag: str | None,
    source_last_modified: str | None,
    status: str,
    total_rows: int,
    active_rows: int,
    disabled_rows: int,
    warning_count: int,
    imported_by_user_id: int | None,
    imported_at: datetime,
) -> AutoreplyRuleSet:
    rule_set = AutoreplyRuleSet(
        source_url=source_url,
        source_checksum=source_checksum,
        source_etag=source_etag,
        source_last_modified=source_last_modified,
        status=status,
        total_rows=total_rows,
        active_rows=active_rows,
        disabled_rows=disabled_rows,
        warning_count=warning_count,
        imported_by_user_id=imported_by_user_id,
        imported_at=imported_at,
    )
    session.add(rule_set)
    await session.flush()
    rule_set.public_id = f"ARS-{rule_set.id:06d}"
    await session.flush()
    return rule_set


async def insert_rules(session: AsyncSession, rules: list[AutoreplyRule]) -> None:
    session.add_all(rules)
    await session.flush()


async def activate_rule_set(
    session: AsyncSession, rule_set: AutoreplyRuleSet, activated_at: datetime
) -> None:
    rule_set.status = "active"
    rule_set.activated_at = activated_at
    await session.flush()


async def supersede_other_active(
    session: AsyncSession, except_rule_set_id: int
) -> None:
    await session.execute(
        update(AutoreplyRuleSet)
        .where(
            AutoreplyRuleSet.status == "active",
            AutoreplyRuleSet.id != except_rule_set_id,
        )
        .values(status="superseded")
    )
    await session.flush()


async def find_active_rule_set(session: AsyncSession) -> AutoreplyRuleSet | None:
    result = await session.execute(
        select(AutoreplyRuleSet)
        .where(AutoreplyRuleSet.status == "active")
        .order_by(AutoreplyRuleSet.id.desc())
    )
    return result.scalars().first()


async def find_rule_set_by_id(
    session: AsyncSession, rule_set_id: int
) -> AutoreplyRuleSet | None:
    result = await session.execute(
        select(AutoreplyRuleSet).where(AutoreplyRuleSet.id == rule_set_id)
    )
    return result.scalar_one_or_none()


async def find_rules_by_rule_set_id(
    session: AsyncSession, rule_set_id: int, *, only_enabled: bool = False
) -> list[AutoreplyRule]:
    stmt = (
        select(AutoreplyRule)
        .where(AutoreplyRule.rule_set_id == rule_set_id)
        .order_by(AutoreplyRule.source_row.asc())
    )
    if only_enabled:
        stmt = stmt.where(AutoreplyRule.disabled.is_(False))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_old_rule_set_ids_beyond_retention(
    session: AsyncSession, keep_superseded: int
) -> list[int]:
    """ID rule set berstatus `superseded` di luar `keep_superseded` yang
    paling baru diaktifkan. Snapshot `active` tidak pernah masuk daftar ini
    (difilter status), jadi pemanggil yang menghitung
    `AUTOREPLY_KEEP_SNAPSHOTS - 1` (total snapshot dikurangi satu yang aktif)
    sebelum memanggil fungsi ini."""
    result = await session.execute(
        select(AutoreplyRuleSet.id)
        .where(AutoreplyRuleSet.status == "superseded")
        .order_by(AutoreplyRuleSet.activated_at.desc())
        .offset(max(keep_superseded, 0))
    )
    return [row[0] for row in result.all()]


async def delete_rule_sets_by_ids(session: AsyncSession, ids: list[int]) -> int:
    if not ids:
        return 0
    result = await session.execute(
        select(AutoreplyRuleSet).where(AutoreplyRuleSet.id.in_(ids))
    )
    rule_sets = list(result.scalars().all())
    for rule_set in rule_sets:
        await session.delete(rule_set)
    await session.flush()
    return len(rule_sets)


async def insert_sync_run(
    session: AsyncSession,
    *,
    reason: str,
    triggered_by_user_id: int | None,
    source_url: str,
    status: str,
    started_at: datetime,
) -> AutoreplySyncRun:
    sync_run = AutoreplySyncRun(
        reason=reason,
        triggered_by_user_id=triggered_by_user_id,
        source_url=source_url,
        status=status,
        summary_json={},
        started_at=started_at,
    )
    session.add(sync_run)
    await session.flush()
    sync_run.public_id = f"ASY-{sync_run.id:06d}"
    await session.flush()
    return sync_run


async def update_sync_run(
    session: AsyncSession,
    sync_run: AutoreplySyncRun,
    **fields: object,
) -> None:
    for key, value in fields.items():
        setattr(sync_run, key, value)
    await session.flush()


async def find_recent_sync_run(session: AsyncSession) -> AutoreplySyncRun | None:
    result = await session.execute(
        select(AutoreplySyncRun).order_by(AutoreplySyncRun.id.desc())
    )
    return result.scalars().first()
