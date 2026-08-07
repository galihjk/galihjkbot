from __future__ import annotations

import re

from app.core.enums import AdminRole
from app.modules.admin.presenters import format_admin_help
from app.modules.autoreply.texts import FORMAT_HELP_TEXT, GROUP_COMMAND_USAGE

"""Bot dikonfigurasi `parse_mode=HTML` default (`app/bot/factory.py`) --
teks apa pun yang lolos ke `message.answer()` DIPARSE Telegram sebagai HTML.
Placeholder command semacam `<chat_id>` diartikan sebagai tag pembuka HTML
dan bikin Telegram menolak seluruh pesan (`TelegramBadRequest: can't parse
entities`) -- bug nyata yang pernah kejadian di produksi (lihat
`logs/error.log`, referensi ERR-298255/ERR-D3D8DD, dari command /adminhelp).
Placeholder command HARUS pakai `[...]`, bukan `<...>`."""

_ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "span", "tg-spoiler", "tg-emoji", "a", "code", "pre", "blockquote",
}
_TAG_RE = re.compile(r"</?\s*([a-zA-Z-]+)")


def _find_unsupported_tags(text: str) -> list[str]:
    return [
        match.group(1)
        for match in _TAG_RE.finditer(text)
        if match.group(1).lower() not in _ALLOWED_TAGS
    ]


def test_format_admin_help_has_no_unsupported_html_tags():
    for role in (None, AdminRole.VIEWER, AdminRole.OPERATOR, AdminRole.ADMIN, AdminRole.SUPERADMIN):
        assert _find_unsupported_tags(format_admin_help(role)) == []


def test_autoreply_format_help_has_no_unsupported_html_tags():
    assert _find_unsupported_tags(FORMAT_HELP_TEXT) == []


def test_group_command_usage_has_no_unsupported_html_tags():
    assert _find_unsupported_tags(GROUP_COMMAND_USAGE) == []
