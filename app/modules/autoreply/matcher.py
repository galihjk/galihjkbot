from __future__ import annotations

import unicodedata

from app.modules.autoreply.schemas import CachedAutoreplyRule, MatchResult


def normalize_for_match(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


class MsgCmdRuleMatcher:
    """Pencocokan exact/contains (§8) -- murni fungsi teks, tidak mengakses
    Telegram API atau database."""

    def match(self, rule: CachedAutoreplyRule, text: str) -> MatchResult:
        normalized_message = normalize_for_match(text)
        normalized_trigger = rule.normalized_command

        if rule.match_all:
            if normalized_message == normalized_trigger:
                return MatchResult(matched=True, cmd_prefix="", cmd_suffix="")
            return MatchResult(matched=False)

        index = normalized_message.find(normalized_trigger)
        if index == -1:
            return MatchResult(matched=False)

        # Potong dari teks ASLI (bukan yang sudah dinormalisasi) supaya
        # cmd_prefix/cmd_suffix tetap tampil natural di template hasil
        # render -- offset index tetap valid karena NFKC+casefold pada
        # implementasi Python tidak mengubah panjang untuk kasus umum yang
        # didukung versi pertama (huruf Latin/umum, tanpa karakter yang
        # expand saat casefold).
        end = index + len(normalized_trigger)
        return MatchResult(
            matched=True,
            cmd_prefix=text[:index],
            cmd_suffix=text[end:],
        )
