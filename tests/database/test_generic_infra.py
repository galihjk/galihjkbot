from __future__ import annotations

from types import SimpleNamespace

from app.database.repositories import (
    audit_repository,
    feature_repository,
    group_repository,
    setting_repository,
    user_repository,
)
from app.services import feature_service


async def test_feature_service_fail_closed_when_feature_missing(session_factory):
    async with session_factory() as db_session:
        enabled = await feature_service.is_enabled(db_session, "unknown", None)
        assert enabled is False


async def test_feature_service_global_toggle(session_factory):
    async with session_factory() as db_session:
        await feature_repository.set_feature_enabled(db_session, "autoreply", False)
        await db_session.commit()

    async with session_factory() as db_session:
        assert await feature_service.is_enabled(db_session, "autoreply", None) is False

    async with session_factory() as db_session:
        await feature_repository.set_feature_enabled(db_session, "autoreply", True)
        await db_session.commit()

    async with session_factory() as db_session:
        assert await feature_service.is_enabled(db_session, "autoreply", None) is True


async def test_group_override_wins_over_global(session_factory):
    async with session_factory() as db_session:
        await feature_repository.set_feature_enabled(db_session, "autoreply", True)
        group = await group_repository.upsert_group(
            db_session,
            SimpleNamespace(id=555, title="Grup Test", username=None, type="group"),
        )
        await feature_repository.set_group_feature(
            db_session, group.id, "autoreply", False
        )
        await db_session.commit()
        group_id = group.id

    async with session_factory() as db_session:
        group = await group_repository.find_by_id(db_session, group_id)
        assert await feature_service.is_enabled(db_session, "autoreply", group) is False


async def test_setting_repository_upsert_roundtrip(session_factory):
    async with session_factory() as db_session:
        assert await setting_repository.get_setting(db_session, "autoreply.active_rule_set_id") is None
        await setting_repository.set_setting(db_session, "autoreply.active_rule_set_id", "1")
        await db_session.commit()

    async with session_factory() as db_session:
        value = await setting_repository.get_setting(db_session, "autoreply.active_rule_set_id")
        assert value == "1"
        await setting_repository.set_setting(db_session, "autoreply.active_rule_set_id", "2")
        await db_session.commit()

    async with session_factory() as db_session:
        assert await setting_repository.get_setting(db_session, "autoreply.active_rule_set_id") == "2"


async def test_audit_repository_records_entry(session_factory):
    async with session_factory() as db_session:
        user = await user_repository.get_or_create_virtual_player(db_session, 0)
        await db_session.commit()
        actor_id = user.id

    async with session_factory() as db_session:
        entry = await audit_repository.record(
            db_session,
            actor_user_id=actor_id,
            action="autoreply.enable_global",
            entity_type="feature",
            entity_id="autoreply",
            old_value=False,
            new_value=True,
        )
        await db_session.commit()
        assert entry.id is not None
        assert entry.old_value_json is False
        assert entry.new_value_json is True
