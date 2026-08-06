from __future__ import annotations

import html
import re

from app.modules.autoreply.constants import ALLOWED_BUTTON_SCHEMES, TELEGRAM_TEXT_LIMIT
from app.modules.autoreply.exceptions import AutoreplyTemplateError
from app.modules.autoreply.schemas import (
    ParsedButton,
    RenderedTextResponse,
    TemplateContext,
)

# Semua pasangan tag kondisi (§10.6-10.9) -- (nama_true, nama_false).
_CONDITION_PAIR_TAGS = (
    "isreply",
    "obj=sbj",
    "ada_ket",
    "ada_dpn",
    "ada_sbj_un",
    "ada_obj_un",
    "ada_rep_txt",
)
_CONDITION_NEGATIVE_TAGS = {
    "isreply": "isnotreply",
    "obj=sbj": "obj!=sbj",
    "ada_ket": "tdk_ada_ket",
    "ada_dpn": "tdk_ada_dpn",
    "ada_sbj_un": "tdk_ada_sbj_un",
    "ada_obj_un": "tdk_ada_obj_un",
    "ada_rep_txt": "tdk_ada_rep_txt",
}
_ALL_PAIRED_TAGS = tuple(_CONDITION_PAIR_TAGS) + tuple(_CONDITION_NEGATIVE_TAGS.values())

_OBJ_SBJ_AS_RE = re.compile(r"\(obj=sbj_as_(.*?)\)", re.DOTALL)
_MENTION_SBJ_RE = re.compile(r"@sbj\((.*?)\)@", re.DOTALL)
_MENTION_OBJ_RE = re.compile(r"@obj\((.*?)\)@", re.DOTALL)
_BUTTON_RE = re.compile(r"\(btn=([^)]+)\)(.*?)\(/btn\)", re.DOTALL)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

_PLACEHOLDER_ORDER = (
    "sbj_dpn",
    "sbj_blk",
    "sbj_un",
    "sbj_id",
    "sbj",
    "obj_dpn",
    "obj_blk",
    "obj_un",
    "obj_id",
    "obj",
    "rep_txt",
    "cmd_dpn",
    "cmd_ket",
)


def _tag_pair_regex(tag_true: str, tag_false: str) -> re.Pattern[str]:
    escaped = re.escape(tag_true)
    return re.compile(rf"\({escaped}\)(.*?)\(/{escaped}\)", re.DOTALL), re.compile(
        rf"\({re.escape(tag_false)}\)(.*?)\(/{re.escape(tag_false)}\)", re.DOTALL
    )


def _placeholder_values(context: TemplateContext) -> dict[str, str]:
    subject = context.subject
    obj = context.object
    return {
        "sbj": html.escape(_full_name(subject), quote=True),
        "sbj_dpn": html.escape(subject.first_name if subject else "", quote=True),
        "sbj_blk": html.escape(subject.last_name if subject else "", quote=True),
        "sbj_un": html.escape(subject.username if subject else "", quote=True),
        "sbj_id": str(subject.id) if subject and subject.id is not None else "",
        "obj": html.escape(_full_name(obj), quote=True),
        "obj_dpn": html.escape(obj.first_name if obj else "", quote=True),
        "obj_blk": html.escape(obj.last_name if obj else "", quote=True),
        "obj_un": html.escape(obj.username if obj else "", quote=True),
        "obj_id": str(obj.id) if obj and obj.id is not None else "",
        "rep_txt": html.escape(context.reply_text, quote=True),
        "cmd_dpn": html.escape(context.cmd_prefix, quote=True),
        "cmd_ket": html.escape(context.cmd_suffix, quote=True),
    }


def _full_name(user) -> str:  # noqa: ANN001 -- TemplateUser | None
    if user is None:
        return ""
    return " ".join(part for part in (user.first_name, user.last_name) if part).strip()


def _has_username(user) -> bool:  # noqa: ANN001
    return bool(user and user.username)


def _is_equal(subject, obj) -> bool:  # noqa: ANN001
    if subject is None or obj is None:
        return False
    if subject.id is None or obj.id is None:
        return False
    return subject.id == obj.id


class MsgCmdTemplateRenderer:
    """Grammar template §10, dijalankan sebagai regex pass berurutan sesuai
    urutan wajib §10.11. Render dipanggil maksimum ~20x/pesan (dibatasi
    `AUTOREPLY_MAX_RESPONSES_PER_MESSAGE`) jadi biaya regex per-panggilan
    diterima tanpa compiled-AST."""

    def render(self, template: str, context: TemplateContext) -> RenderedTextResponse:
        text = template

        text = self._apply_pair(text, "isreply", "isnotreply", context.has_reply)
        text = self._apply_pair(
            text, "obj=sbj", "obj!=sbj", _is_equal(context.subject, context.object)
        )
        text = self._apply_pair(
            text, "ada_ket", "tdk_ada_ket", context.cmd_suffix != ""
        )
        text = self._apply_pair(
            text, "ada_dpn", "tdk_ada_dpn", context.cmd_prefix != ""
        )
        text = self._apply_pair(
            text, "ada_sbj_un", "tdk_ada_sbj_un", _has_username(context.subject)
        )
        text = self._apply_pair(
            text, "ada_obj_un", "tdk_ada_obj_un", _has_username(context.object)
        )
        text = self._apply_pair(
            text, "ada_rep_txt", "tdk_ada_rep_txt", context.reply_text != ""
        )

        equal = _is_equal(context.subject, context.object)
        text = _OBJ_SBJ_AS_RE.sub(lambda m: m.group(1) if equal else "", text)

        placeholders = _placeholder_values(context)
        for name in _PLACEHOLDER_ORDER:
            text = text.replace(f"({name})", placeholders[name])

        text = _MENTION_SBJ_RE.sub(
            lambda m: _render_mention(context.subject, m.group(1)), text
        )
        text = _MENTION_OBJ_RE.sub(
            lambda m: _render_mention(context.object, m.group(1)), text
        )

        buttons: list[ParsedButton] = []

        def _extract_button(match: re.Match[str]) -> str:
            url = match.group(1).strip()
            label = match.group(2).strip()
            buttons.append(ParsedButton(label=label, url=url))
            return ""

        text = _BUTTON_RE.sub(_extract_button, text)

        if len(text) > TELEGRAM_TEXT_LIMIT:
            raise AutoreplyTemplateError(
                f"Hasil render {len(text)} karakter melebihi batas Telegram "
                f"{TELEGRAM_TEXT_LIMIT}."
            )

        return RenderedTextResponse(text=text, buttons=tuple(buttons))

    @staticmethod
    def _apply_pair(text: str, tag_true: str, tag_false: str, condition: bool) -> str:
        re_true, re_false = _tag_pair_regex(tag_true, tag_false)
        text = re_true.sub(lambda m: m.group(1) if condition else "", text)
        text = re_false.sub(lambda m: m.group(1) if not condition else "", text)
        return text


def _render_mention(user, label: str) -> str:  # noqa: ANN001
    if user is None or user.id is None:
        return ""
    return f'<a href="tg://user?id={user.id}">{html.escape(label, quote=True)}</a>'


def validate_template_structure(template: str) -> list[str]:
    """Validasi statis saat sync (§10.11 langkah 8 + §9.3): pasangan tag
    seimbang & tidak nested, URL tombol valid, dan teks tidak kosong setelah
    tombol dihapus. TIDAK butuh `TemplateContext` -- ini cek bentuk, bukan
    hasil render untuk pesan tertentu."""
    errors: list[str] = []

    for tag in _ALL_PAIRED_TAGS:
        open_count = len(re.findall(rf"\({re.escape(tag)}\)", template))
        close_count = len(re.findall(rf"\(/{re.escape(tag)}\)", template))
        if open_count != close_count:
            errors.append(
                f"Tag ({tag}) tidak seimbang: {open_count} pembuka, {close_count} penutup."
            )

    if _has_nested_tags(template):
        errors.append("Blok kondisi bersarang (nested) tidak diperbolehkan.")

    remaining = template
    for match in _BUTTON_RE.finditer(template):
        url = match.group(1).strip()
        label = match.group(2).strip()
        if not label:
            errors.append("Label tombol tidak boleh kosong.")
        scheme = url.split(":", 1)[0].lower() if ":" in url else ""
        if scheme not in ALLOWED_BUTTON_SCHEMES:
            errors.append(
                f"URL tombol '{url}' harus berskema {'/'.join(ALLOWED_BUTTON_SCHEMES)}."
            )
        if _CONTROL_CHAR_RE.search(url):
            errors.append(f"URL tombol '{url}' mengandung control character.")

    remaining = _BUTTON_RE.sub("", remaining)
    stripped_of_tags = re.sub(r"\(/?[^()]*\)", "", remaining)
    if stripped_of_tags.strip() == "":
        errors.append(
            "Rule hanya berisi tombol/tag kosong -- teks hasil akhir tidak boleh kosong."
        )

    return errors


def _has_nested_tags(template: str) -> bool:
    """Deteksi tag pembuka jenis A yang muncul sebelum tag penutup jenis A
    yang sedang terbuka ditutup, sementara tag jenis B (apa pun) dibuka DI
    ANTARANYA -- pendekatan sederhana: untuk tiap jenis tag, ambil semua
    span (pembuka..penutup) urut kemunculan; kalau ada span tag lain yang
    dimulai strictly di dalam span tersebut, itu nested."""
    spans: list[tuple[int, int]] = []
    for tag in _ALL_PAIRED_TAGS:
        open_re = re.compile(rf"\({re.escape(tag)}\)")
        close_re = re.compile(rf"\(/{re.escape(tag)}\)")
        opens = [m.start() for m in open_re.finditer(template)]
        closes = [m.start() for m in close_re.finditer(template)]
        for open_pos, close_pos in zip(opens, closes):
            if open_pos < close_pos:
                spans.append((open_pos, close_pos))

    spans.sort()
    for i, (start_a, end_a) in enumerate(spans):
        for start_b, end_b in spans[i + 1 :]:
            if start_b < end_a and start_b > start_a and end_b <= end_a:
                return True
            if start_b < end_a and end_b > end_a:
                return True
    return False
