from __future__ import annotations

from app.core.enums import AdminRole
from app.modules.admin.presenters import format_admin_help


class RecordingMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


def test_viewer_sees_locked_marks_on_higher_tier_commands():
    text = format_admin_help(AdminRole.VIEWER)
    assert "✅ /msgcmd_status" in text
    assert "🔒 /msgcmd_reload" in text
    assert "🔒 /msgcmd_enable" in text


def test_operator_unlocks_operator_tier_but_not_admin_tier():
    text = format_admin_help(AdminRole.OPERATOR)
    assert "✅ /msgcmd_reload" in text
    assert "🔒 /msgcmd_enable" in text


def test_admin_unlocks_everything_listed():
    text = format_admin_help(AdminRole.ADMIN)
    assert "🔒 /" not in text


def test_none_role_shows_dash_and_all_locked_except_none():
    text = format_admin_help(None)
    assert "Role kamu: -" in text


async def test_handler_replies_with_generated_text():
    from app.modules.admin.handlers.help import handle_admin_help

    message = RecordingMessage()
    await handle_admin_help(message, AdminRole.OPERATOR)
    assert message.answers == [format_admin_help(AdminRole.OPERATOR)]
