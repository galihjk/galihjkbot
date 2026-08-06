from __future__ import annotations

from app.modules.autoreply.matcher import MsgCmdRuleMatcher
from app.modules.autoreply.schemas import CachedAutoreplyRule

matcher = MsgCmdRuleMatcher()


def _rule(command: str, *, match_all: bool) -> CachedAutoreplyRule:
    from app.modules.autoreply.matcher import normalize_for_match

    return CachedAutoreplyRule(
        id=1,
        rule_set_id=1,
        source_row=1,
        command=command,
        normalized_command=normalize_for_match(command),
        message_template="x",
        response_type="text",
        media_file_id=None,
        match_all=match_all,
        reply_to_sender=False,
        reply_to_replied=False,
        admin_only=False,
    )


def test_exact_matches_regardless_of_case():
    rule = _rule("halo", match_all=True)
    assert matcher.match(rule, "HALO").matched is True


def test_exact_rejects_extra_prefix_or_suffix():
    rule = _rule("halo", match_all=True)
    assert matcher.match(rule, "halo semua").matched is False
    assert matcher.match(rule, "eh halo").matched is False


def test_contains_matches_at_start_middle_end():
    rule = _rule("peluk", match_all=False)
    assert matcher.match(rule, "peluk dia").matched is True
    assert matcher.match(rule, "dia peluk aku").matched is True
    assert matcher.match(rule, "dia mau peluk").matched is True


def test_contains_uses_first_occurrence_for_prefix_suffix():
    rule = _rule("peluk", match_all=False)
    result = matcher.match(rule, "Rani peluk Budi")
    assert result.matched is True
    assert result.cmd_prefix == "Rani "
    assert result.cmd_suffix == " Budi"


def test_contains_no_match_returns_false():
    rule = _rule("peluk", match_all=False)
    assert matcher.match(rule, "halo semua").matched is False


def test_unicode_nfkc_and_casefold():
    rule = _rule("café", match_all=True)
    # "é" via kombinasi NFKC harus tetap cocok dengan bentuk composed.
    assert matcher.match(rule, "CAFÉ").matched is True


def test_admin_only_flag_preserved_on_rule():
    rule = _rule("admin test", match_all=True)
    assert rule.admin_only is False
