from __future__ import annotations

from types import SimpleNamespace

from app.core.maintenance import MaintenanceGate
from app.modules.autoreply.handlers import handle_autoreply_message


class RecordingAutoreplyService:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def handle_message(self, message, db_session, current_group, admin_role):
        self.calls.append(message)


async def test_autoreply_skipped_during_maintenance():
    gate = MaintenanceGate()
    gate.active = True
    service = RecordingAutoreplyService()
    message = SimpleNamespace(text="halo")

    await handle_autoreply_message(message, db_session=None, autoreply_service=service, maintenance_gate=gate)

    assert service.calls == []


async def test_autoreply_works_normally_when_gate_inactive():
    gate = MaintenanceGate()
    service = RecordingAutoreplyService()
    message = SimpleNamespace(text="halo")

    await handle_autoreply_message(message, db_session=None, autoreply_service=service, maintenance_gate=gate)

    assert service.calls == [message]
