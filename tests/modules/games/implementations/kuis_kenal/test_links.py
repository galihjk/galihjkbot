from __future__ import annotations

from app.modules.games.implementations.kuis_kenal.links import (
    build_deep_link_payload,
    parse_deep_link_payload,
)


def test_roundtrip_all_purposes():
    for purpose in ("question_select", "answer", "judge"):
        payload = build_deep_link_payload(purpose, session_id=42, round_number=3, nonce="abcd1234")
        parsed = parse_deep_link_payload(payload)
        assert parsed is not None
        assert parsed.purpose == purpose
        assert parsed.session_id == 42
        assert parsed.round_number == 3
        assert parsed.nonce == "abcd1234"


def test_large_session_id_roundtrips():
    payload = build_deep_link_payload("answer", session_id=123456789, round_number=17, nonce="zz")
    parsed = parse_deep_link_payload(payload)
    assert parsed.session_id == 123456789
    assert parsed.round_number == 17


def test_rejects_unknown_prefix():
    assert parse_deep_link_payload("other-x-1-1-abc") is None


def test_rejects_malformed_payload():
    assert parse_deep_link_payload("kk-a-1-1") is None  # kurang bagian
    assert parse_deep_link_payload("kk-x-1-1-abc") is None  # kode tidak dikenal
    assert parse_deep_link_payload("kk-a-1-1-") is None  # nonce kosong
    assert parse_deep_link_payload("kk-a-!!-1-abc") is None  # bukan base36 valid


def test_payload_starts_with_prefix():
    payload = build_deep_link_payload("question_select", session_id=1, round_number=1, nonce="x")
    assert payload.startswith("kk-q-")
