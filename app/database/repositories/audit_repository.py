from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log_entry import AuditLogEntry


async def record(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    old_value: object | None = None,
    new_value: object | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value_json=old_value,
        new_value_json=new_value,
    )
    session.add(entry)
    await session.flush()
    return entry
