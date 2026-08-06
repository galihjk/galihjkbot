from __future__ import annotations

import csv
import io
import unicodedata

from app.modules.autoreply.constants import (
    BOOLEAN_COLUMNS,
    MEDIA_PREFIXES,
    REQUIRED_HEADERS,
    RESPONSE_TYPE_TEXT,
)
from app.modules.autoreply.exceptions import AutoreplyCSVParseError, AutoreplyHeaderError
from app.modules.autoreply.schemas import ParsedDocument, ValidatedRuleRow, ValidationIssue
from app.modules.autoreply.template_renderer import validate_template_structure


def normalize_boolean(raw: str) -> bool | None:
    """§7.3: TRUE (apa pun casing/spasi sekitarnya) -> True; kosong/FALSE
    -> False; nilai lain -> None (invalid, jadi error baris oleh pemanggil)."""
    stripped = raw.strip()
    if stripped == "":
        return False
    folded = stripped.casefold()
    if folded == "true":
        return True
    if folded == "false":
        return False
    return None


def _read_csv_rows(content: bytes) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AutoreplyCSVParseError(f"Gagal decode CSV sebagai UTF-8: {exc}") from exc

    try:
        reader = csv.reader(io.StringIO(text))
        raw_rows = list(reader)
    except csv.Error as exc:
        raise AutoreplyCSVParseError(f"Gagal parse CSV: {exc}") from exc

    if not raw_rows:
        raise AutoreplyCSVParseError("CSV kosong, tidak ada header.")

    header = [cell.strip() for cell in raw_rows[0]]
    # Nama header tidak dipangkas isinya sendiri secara case, cuma whitespace
    # di kiri/kanan -- §7.3 "nama header tidak dipangkas atau diubah" berarti
    # tidak di-lower/rename, bukan berarti whitespace liar dipertahankan.

    rows: list[tuple[int, dict[str, str]]] = []
    for position, raw_row in enumerate(raw_rows[1:], start=1):
        if all(cell.strip() == "" for cell in raw_row):
            continue
        values = [cell.strip() for cell in raw_row]
        # Baris lebih pendek dari header -> field yang hilang dianggap "".
        padded = values + [""] * (len(header) - len(values))
        row_dict = dict(zip(header, padded))
        rows.append((position, row_dict))

    return header, rows


def _validate_header(header: list[str]) -> None:
    missing = [name for name in REQUIRED_HEADERS if name not in header]
    if missing:
        raise AutoreplyHeaderError(
            "Header wajib hilang: " + ", ".join(missing)
        )


def _detect_response(
    message: str,
) -> tuple[str, str | None, str]:
    """Return (response_type, media_file_id, message_template_for_storage)."""
    for prefix, response_type in MEDIA_PREFIXES.items():
        if message.startswith(prefix):
            file_id = message[len(prefix):].strip()
            return response_type, file_id, message
    return RESPONSE_TYPE_TEXT, None, message


def parse_and_validate(content: bytes) -> ParsedDocument:
    """Parse CSV + validasi header/baris (§7, §9.2, §9.3). Kebijakan strict
    snapshot (§7.4): kalau ada SATU error baris pun, `ParsedDocument.errors`
    tidak kosong dan pemanggil (sync_service) WAJIB menolak seluruh
    snapshot -- fungsi ini sendiri tidak menolak apa pun, cuma melaporkan."""
    header, raw_rows = _read_csv_rows(content)
    _validate_header(header)

    rows: list[ValidatedRuleRow] = []
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for source_row, raw in raw_rows:
        row_errors: list[str] = []

        command = raw.get("Command", "")
        message = raw.get("Message", "")

        if command == "":
            row_errors.append("Command tidak boleh kosong.")
        if message == "":
            row_errors.append("Message tidak boleh kosong.")

        booleans: dict[str, bool] = {}
        for column in BOOLEAN_COLUMNS:
            value = normalize_boolean(raw.get(column, ""))
            if value is None:
                row_errors.append(
                    f"Nilai {column} harus TRUE, FALSE, atau kosong."
                )
            else:
                booleans[column] = value

        response_type = RESPONSE_TYPE_TEXT
        media_file_id: str | None = None
        if message:
            response_type, media_file_id, _ = _detect_response(message)
            if response_type != RESPONSE_TYPE_TEXT and not media_file_id:
                row_errors.append(
                    f"Prefix media pada baris ini tidak diikuti file_id."
                )
            if response_type == RESPONSE_TYPE_TEXT:
                row_errors.extend(
                    f"Template tidak valid: {issue}"
                    for issue in validate_template_structure(message)
                )

        if booleans.get("ReplyToSender") and booleans.get("ReplyToReplied"):
            warnings.append(
                ValidationIssue(
                    source_row=source_row,
                    message="ReplyToSender dan ReplyToReplied sama-sama TRUE; "
                    "ReplyToSender diprioritaskan saat runtime.",
                )
            )

        if row_errors:
            errors.extend(
                ValidationIssue(source_row=source_row, message=msg)
                for msg in row_errors
            )
            continue

        normalized_command = unicodedata.normalize("NFKC", command).casefold()
        rows.append(
            ValidatedRuleRow(
                source_row=source_row,
                command=command,
                normalized_command=normalized_command,
                message_template=message,
                response_type=response_type,
                media_file_id=media_file_id,
                match_all=booleans["MatchAll"],
                reply_to_sender=booleans["ReplyToSender"],
                reply_to_replied=booleans["ReplyToReplied"],
                admin_only=booleans["AdminOnly"],
                disabled=booleans["Disabled"],
                source_payload=dict(raw),
            )
        )

    return ParsedDocument(
        rows=tuple(rows),
        errors=tuple(errors),
        warnings=tuple(warnings),
        total_rows=len(raw_rows),
    )
