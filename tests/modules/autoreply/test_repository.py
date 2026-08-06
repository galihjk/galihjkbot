from __future__ import annotations

from datetime import datetime, timedelta

from app.database.models.autoreply_rule import AutoreplyRule
from app.database.repositories import autoreply_repository


def _make_rule(rule_set_id: int, source_row: int, command: str = "halo") -> AutoreplyRule:
    return AutoreplyRule(
        rule_set_id=rule_set_id,
        source_row=source_row,
        command=command,
        normalized_command=command.casefold(),
        message_template="Halo, (sbj_dpn)!",
        response_type="text",
        media_file_id=None,
        match_all=True,
        reply_to_sender=True,
        reply_to_replied=False,
        admin_only=False,
        disabled=False,
        source_payload_json={"Command": command},
    )


async def test_insert_rule_set_assigns_public_id(session_factory):
    async with session_factory() as db_session:
        rule_set = await autoreply_repository.insert_rule_set(
            db_session,
            source_url="https://example.com/sheet.csv",
            source_checksum="abc123",
            source_etag=None,
            source_last_modified=None,
            status="active",
            total_rows=1,
            active_rows=1,
            disabled_rows=0,
            warning_count=0,
            imported_by_user_id=None,
            imported_at=datetime(2026, 8, 6, 10, 0, 0),
        )
        await db_session.commit()
        assert rule_set.public_id == f"ARS-{rule_set.id:06d}"


async def test_insert_and_find_rules_ordered_by_source_row(session_factory):
    async with session_factory() as db_session:
        rule_set = await autoreply_repository.insert_rule_set(
            db_session,
            source_url="https://example.com/sheet.csv",
            source_checksum="abc123",
            source_etag=None,
            source_last_modified=None,
            status="active",
            total_rows=2,
            active_rows=1,
            disabled_rows=1,
            warning_count=0,
            imported_by_user_id=None,
            imported_at=datetime(2026, 8, 6, 10, 0, 0),
        )
        rule_a = _make_rule(rule_set.id, 2, "kedua")
        rule_b = _make_rule(rule_set.id, 1, "pertama")
        rule_b.disabled = True
        await autoreply_repository.insert_rules(db_session, [rule_a, rule_b])
        await db_session.commit()
        rule_set_id = rule_set.id

    async with session_factory() as db_session:
        all_rules = await autoreply_repository.find_rules_by_rule_set_id(
            db_session, rule_set_id
        )
        assert [rule.command for rule in all_rules] == ["pertama", "kedua"]

        enabled_only = await autoreply_repository.find_rules_by_rule_set_id(
            db_session, rule_set_id, only_enabled=True
        )
        assert [rule.command for rule in enabled_only] == ["kedua"]


async def test_activate_rule_set_supersedes_previous_active(session_factory):
    async with session_factory() as db_session:
        first = await autoreply_repository.insert_rule_set(
            db_session,
            source_url="https://example.com/sheet.csv",
            source_checksum="v1",
            source_etag=None,
            source_last_modified=None,
            status="active",
            total_rows=0,
            active_rows=0,
            disabled_rows=0,
            warning_count=0,
            imported_by_user_id=None,
            imported_at=datetime(2026, 8, 6, 9, 0, 0),
        )
        await autoreply_repository.activate_rule_set(
            db_session, first, datetime(2026, 8, 6, 9, 0, 0)
        )
        await db_session.commit()
        first_id = first.id

        second = await autoreply_repository.insert_rule_set(
            db_session,
            source_url="https://example.com/sheet.csv",
            source_checksum="v2",
            source_etag=None,
            source_last_modified=None,
            status="pending",
            total_rows=0,
            active_rows=0,
            disabled_rows=0,
            warning_count=0,
            imported_by_user_id=None,
            imported_at=datetime(2026, 8, 6, 10, 0, 0),
        )
        await autoreply_repository.activate_rule_set(
            db_session, second, datetime(2026, 8, 6, 10, 0, 0)
        )
        await autoreply_repository.supersede_other_active(db_session, second.id)
        await db_session.commit()
        second_id = second.id

    async with session_factory() as db_session:
        active = await autoreply_repository.find_active_rule_set(db_session)
        assert active.id == second_id

        old = await autoreply_repository.find_rule_set_by_id(db_session, first_id)
        assert old.status == "superseded"


async def test_retention_keeps_latest_n_superseded_and_cascades_rule_delete(
    session_factory,
):
    async with session_factory() as db_session:
        base_time = datetime(2026, 8, 1, 0, 0, 0)
        rule_set_ids = []
        for i in range(4):
            rule_set = await autoreply_repository.insert_rule_set(
                db_session,
                source_url="https://example.com/sheet.csv",
                source_checksum=f"v{i}",
                source_etag=None,
                source_last_modified=None,
                status="superseded",
                total_rows=1,
                active_rows=1,
                disabled_rows=0,
                warning_count=0,
                imported_by_user_id=None,
                imported_at=base_time + timedelta(hours=i),
            )
            rule_set.activated_at = base_time + timedelta(hours=i)
            await autoreply_repository.insert_rules(
                db_session, [_make_rule(rule_set.id, 1)]
            )
            rule_set_ids.append(rule_set.id)
        await db_session.commit()

    async with session_factory() as db_session:
        # keep_superseded=2 -> hanya 2 rule set superseded TERBARU yang
        # dipertahankan, 2 yang paling lama (index 0 dan 1) jadi kandidat hapus.
        stale_ids = await autoreply_repository.find_old_rule_set_ids_beyond_retention(
            db_session, keep_superseded=2
        )
        assert set(stale_ids) == {rule_set_ids[0], rule_set_ids[1]}

        deleted_count = await autoreply_repository.delete_rule_sets_by_ids(
            db_session, stale_ids
        )
        await db_session.commit()
        assert deleted_count == 2

    async with session_factory() as db_session:
        remaining = await autoreply_repository.find_rules_by_rule_set_id(
            db_session, rule_set_ids[0]
        )
        assert remaining == []


async def test_sync_run_lifecycle(session_factory):
    async with session_factory() as db_session:
        sync_run = await autoreply_repository.insert_sync_run(
            db_session,
            reason="manual",
            triggered_by_user_id=None,
            source_url="https://example.com/sheet.csv",
            status="running",
            started_at=datetime(2026, 8, 6, 10, 0, 0),
        )
        await db_session.commit()
        assert sync_run.public_id == f"ASY-{sync_run.id:06d}"
        sync_run_id = sync_run.id

    async with session_factory() as db_session:
        sync_run = await autoreply_repository.find_recent_sync_run(db_session)
        assert sync_run.id == sync_run_id

        await autoreply_repository.update_sync_run(
            db_session,
            sync_run,
            status="success",
            finished_at=datetime(2026, 8, 6, 10, 0, 5),
            total_rows=3,
        )
        await db_session.commit()

    async with session_factory() as db_session:
        sync_run = await autoreply_repository.find_recent_sync_run(db_session)
        assert sync_run.status == "success"
        assert sync_run.total_rows == 3
