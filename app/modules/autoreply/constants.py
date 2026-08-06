from __future__ import annotations

from aiogram.enums import ChatType

from app.core.enums import AdminRole

FEATURE_KEY = "autoreply"

REQUIRED_HEADERS = (
    "Command",
    "Message",
    "MatchAll",
    "ReplyToSender",
    "ReplyToReplied",
    "AdminOnly",
    "Disabled",
)

BOOLEAN_COLUMNS = ("MatchAll", "ReplyToSender", "ReplyToReplied", "AdminOnly", "Disabled")

# Prefix respons media (§9.1) -> nama response_type yang disimpan di DB dan
# nama method aiogram yang dipakai `AutoreplyResponseSender`.
MEDIA_PREFIXES: dict[str, str] = {
    "*voice:": "voice",
    "*document:": "document",
    "*photo:": "photo",
    "*video:": "video",
    "*audio:": "audio",
    "*sticker:": "sticker",
}
RESPONSE_TYPE_TEXT = "text"

ALLOWED_BUTTON_SCHEMES = ("https", "http", "tg")

TELEGRAM_TEXT_LIMIT = 4096

# Tabel permission §20.1 dokumen desain cuma 3 tier -- dipetakan langsung ke
# AdminRole minimum yang sudah dipakai filter `IsAdmin` di modul admin lain,
# tanpa membuat sistem dotted-permission baru.
PERMISSION_VIEW_STATUS = AdminRole.VIEWER
PERMISSION_VIEW_FORMAT = AdminRole.VIEWER
PERMISSION_VIEW_SYNC_ERRORS = AdminRole.VIEWER
PERMISSION_TRIGGER_ADMIN_RULE = AdminRole.OPERATOR
PERMISSION_RELOAD = AdminRole.OPERATOR
PERMISSION_TOGGLE_GROUP = AdminRole.OPERATOR
PERMISSION_EXTRACT_MEDIA_CODE = AdminRole.OPERATOR
PERMISSION_TOGGLE_GLOBAL = AdminRole.ADMIN

DEFAULT_SNAPSHOT_STATUS_ACTIVE = "active"
DEFAULT_SNAPSHOT_STATUS_SUPERSEDED = "superseded"
DEFAULT_SNAPSHOT_STATUS_ARCHIVED = "archived"

SYNC_REASON_STARTUP = "startup"
SYNC_REASON_MANUAL = "manual"
SYNC_REASON_SCHEDULED = "scheduled"

SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_SUCCESS = "success"
SYNC_STATUS_FAILED = "failed"
SYNC_STATUS_UNCHANGED = "unchanged"

SETTING_ACTIVE_RULE_SET_ID = "autoreply.active_rule_set_id"
SETTING_LAST_SUCCESSFUL_SYNC_AT = "autoreply.last_successful_sync_at"
SETTING_LAST_SYNC_STATUS = "autoreply.last_sync_status"

ALLOWED_CHAT_TYPES_GROUP = (ChatType.GROUP, ChatType.SUPERGROUP)
