from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TemplateUser:
    id: int | None
    first_name: str
    last_name: str
    username: str


@dataclass(frozen=True)
class TemplateContext:
    subject: TemplateUser | None
    object: TemplateUser | None
    reply_text: str
    cmd_prefix: str
    cmd_suffix: str
    # Doc dataclass §10.1 tidak punya field ini, tapi tanpanya "isreply"
    # tidak bisa dibedakan dari "reply ke pesan tanpa from_user" (object
    # jadi TemplateUser kosong, bukan None -- §10.1 baris terakhir). Field
    # ini murni menandai keberadaan `message.reply_to_message`.
    has_reply: bool = False


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    cmd_prefix: str = ""
    cmd_suffix: str = ""


@dataclass(frozen=True)
class CachedAutoreplyRule:
    id: int
    rule_set_id: int
    source_row: int
    command: str
    normalized_command: str
    message_template: str
    response_type: str
    media_file_id: str | None
    match_all: bool
    reply_to_sender: bool
    reply_to_replied: bool
    admin_only: bool


@dataclass(frozen=True)
class AutoreplyCacheSnapshot:
    rule_set_id: int | None
    public_id: str | None
    checksum: str | None
    activated_at: datetime | None
    rules: tuple[CachedAutoreplyRule, ...]

    @classmethod
    def empty(cls) -> "AutoreplyCacheSnapshot":
        return cls(
            rule_set_id=None, public_id=None, checksum=None, activated_at=None, rules=()
        )

    @property
    def is_empty(self) -> bool:
        return self.rule_set_id is None


@dataclass(frozen=True)
class ParsedButton:
    label: str
    url: str


@dataclass(frozen=True)
class RenderedTextResponse:
    text: str
    buttons: tuple[ParsedButton, ...] = ()


@dataclass(frozen=True)
class SendResult:
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class AutoreplyExecutionResult:
    status: str
    reason: str | None = None
    matched_rules_count: int = 0
    sent_rules_count: int = 0

    @classmethod
    def skipped(cls, reason: str) -> "AutoreplyExecutionResult":
        return cls(status="skipped", reason=reason)

    @classmethod
    def from_counts(
        cls, matched_rules_count: int, sent_rules_count: int
    ) -> "AutoreplyExecutionResult":
        return cls(
            status="processed",
            matched_rules_count=matched_rules_count,
            sent_rules_count=sent_rules_count,
        )


@dataclass(frozen=True)
class ValidationIssue:
    source_row: int | None
    message: str


@dataclass(frozen=True)
class ValidatedRuleRow:
    source_row: int
    command: str
    normalized_command: str
    message_template: str
    response_type: str
    media_file_id: str | None
    match_all: bool
    reply_to_sender: bool
    reply_to_replied: bool
    admin_only: bool
    disabled: bool
    source_payload: dict


@dataclass(frozen=True)
class ParsedDocument:
    rows: tuple[ValidatedRuleRow, ...]
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]
    total_rows: int

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class RawSource:
    content: bytes
    checksum: str
    etag: str | None
    last_modified: str | None
    http_status: int


@dataclass(frozen=True)
class AutoreplySyncResult:
    status: str
    public_id: str | None = None
    error_reference: str | None = None
    total_rows: int | None = None
    active_rows: int | None = None
    disabled_rows: int | None = None
    warning_count: int = 0
    error_count: int = 0
    duration_ms: float | None = None
    row_errors: tuple[str, ...] = field(default_factory=tuple)
    row_warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AutoreplySnapshotInfo:
    rule_set_id: int
    public_id: str
    status: str
    total_rows: int
    active_rows: int
    disabled_rows: int
    warning_count: int
    source_checksum: str
    activated_at: datetime | None


@dataclass(frozen=True)
class MediaCodeResult:
    success: bool
    code: str | None = None
    error_message: str | None = None
