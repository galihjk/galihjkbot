from __future__ import annotations

from app.core.maintenance import MAINTENANCE_NOTICE, MaintenanceGate
from app.database.models.group import Group
from app.database.models.user import User
from app.modules.games.engine.registry import GameRegistry
from app.modules.games.handlers.commands import handle_game_command, handle_game_menu_selection
from app.modules.games.keyboards.game_menu import GameMenuCallback


class RecordingMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class RecordingCommand:
    def __init__(self, args: str | None = None) -> None:
        self.args = args


class RecordingCallback:
    def __init__(self) -> None:
        self.answers: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


async def test_game_command_blocked_during_maintenance(game_world):
    [user_id] = await game_world.add_players(1)
    gate = MaintenanceGate()
    gate.active = True

    async with game_world.session_factory() as db_session:
        current_user = await db_session.get(User, user_id)
        current_group = await db_session.get(Group, game_world.group_id)
        message = RecordingMessage()

        await handle_game_command(
            message,
            RecordingCommand(args="kuis_kenal"),
            GameRegistry(),
            game_world.manager,
            db_session,
            current_user,
            current_group,
            gate,
        )

    assert message.answers == [MAINTENANCE_NOTICE]
    assert game_world.bot.sent == []  # tidak ada lobby yang dibuat/diumumkan


async def test_game_command_works_normally_when_gate_inactive(game_world):
    [user_id] = await game_world.add_players(1)
    gate = MaintenanceGate()

    async with game_world.session_factory() as db_session:
        current_user = await db_session.get(User, user_id)
        current_group = await db_session.get(Group, game_world.group_id)
        message = RecordingMessage()

        await handle_game_command(
            message,
            RecordingCommand(args="unknown_game_key"),
            GameRegistry(),
            game_world.manager,
            db_session,
            current_user,
            current_group,
            gate,
        )

    # Bukan diblokir maintenance -- lolos ke logic asli & gagal krn game_key
    # tidak dikenal (regresi: perilaku lama tetap jalan saat gate tidak aktif).
    assert message.answers == ["Game tidak ditemukan."]


async def test_game_menu_selection_blocked_during_maintenance(game_world):
    [user_id] = await game_world.add_players(1)
    gate = MaintenanceGate()
    gate.active = True

    async with game_world.session_factory() as db_session:
        current_user = await db_session.get(User, user_id)
        current_group = await db_session.get(Group, game_world.group_id)
        callback = RecordingCallback()

        await handle_game_menu_selection(
            callback,
            GameMenuCallback(game_key="kuis_kenal"),
            game_world.manager,
            db_session,
            current_user,
            current_group,
            gate,
        )

    assert callback.answers == [(MAINTENANCE_NOTICE, True)]
    assert game_world.bot.sent == []
