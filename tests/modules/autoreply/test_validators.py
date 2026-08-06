from __future__ import annotations

import pytest

from app.modules.autoreply.exceptions import AutoreplyCSVParseError, AutoreplyHeaderError
from app.modules.autoreply.validators import normalize_boolean, parse_and_validate

HEADER = "Command,Message,MatchAll,ReplyToSender,ReplyToReplied,AdminOnly,Disabled"


def _csv(*rows: str) -> bytes:
    return ("\n".join([HEADER, *rows])).encode("utf-8")


def test_normalize_boolean_variants():
    assert normalize_boolean("TRUE") is True
    assert normalize_boolean(" true ") is True
    assert normalize_boolean("True") is True
    assert normalize_boolean("FALSE") is False
    assert normalize_boolean("") is False
    assert normalize_boolean("false") is False
    assert normalize_boolean("maybe") is None


def test_valid_document_produces_no_errors():
    content = _csv('halo,"Halo, (sbj_dpn)!",TRUE,TRUE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert doc.is_valid
    assert len(doc.rows) == 1
    row = doc.rows[0]
    assert row.command == "halo"
    assert row.match_all is True
    assert row.response_type == "text"


def test_missing_required_header_raises():
    content = b"Command,Message\nhalo,hai"
    with pytest.raises(AutoreplyHeaderError):
        parse_and_validate(content)


def test_empty_command_is_row_error():
    content = _csv(',hai,TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert not doc.is_valid
    assert any("Command tidak boleh kosong" in issue.message for issue in doc.errors)


def test_empty_message_is_row_error():
    content = _csv('halo,,TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert not doc.is_valid
    assert any("Message tidak boleh kosong" in issue.message for issue in doc.errors)


def test_invalid_boolean_is_row_error():
    content = _csv('halo,hai,YA,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert not doc.is_valid
    assert any("MatchAll" in issue.message for issue in doc.errors)


def test_media_prefix_without_file_id_is_error():
    content = _csv('suara,*voice:,TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert not doc.is_valid


def test_media_prefix_with_file_id_parses_correctly():
    content = _csv('suara,*voice:AwACAgUAAxkBAA,TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert doc.is_valid
    row = doc.rows[0]
    assert row.response_type == "voice"
    assert row.media_file_id == "AwACAgUAAxkBAA"


def test_text_resembling_prefix_but_not_exact_stays_text():
    content = _csv('halo,"*voicemail: bukan media",TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert doc.is_valid
    assert doc.rows[0].response_type == "text"


def test_quoted_comma_and_newline_supported():
    content = _csv('/aturan,"<b>Aturan grup</b>\nBaris kedua, lanjutan",TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert doc.is_valid
    assert "Baris kedua, lanjutan" in doc.rows[0].message_template


def test_utf8_bom_is_handled():
    content = b"\xef\xbb\xbf" + _csv('halo,hai,TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert doc.is_valid


def test_blank_rows_are_skipped_but_source_row_preserves_position():
    content = _csv(
        'pertama,hai,TRUE,FALSE,FALSE,FALSE,FALSE',
        ',,,,,,',
        'ketiga,hai,TRUE,FALSE,FALSE,FALSE,FALSE',
    )
    doc = parse_and_validate(content)
    assert doc.is_valid
    assert [row.source_row for row in doc.rows] == [1, 3]


def test_both_reply_flags_true_produces_warning():
    content = _csv('halo,hai,TRUE,TRUE,TRUE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert doc.is_valid
    assert any("ReplyToSender dan ReplyToReplied" in w.message for w in doc.warnings)


def test_unbalanced_template_tag_is_row_error():
    content = _csv('halo,"(isreply)hai",TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert not doc.is_valid


def test_invalid_button_scheme_is_row_error():
    content = _csv('halo,"(btn=ftp://x)Klik(/btn)teks",TRUE,FALSE,FALSE,FALSE,FALSE')
    doc = parse_and_validate(content)
    assert not doc.is_valid


def test_disabled_row_still_parsed_but_flagged():
    content = _csv('arsip,tidak aktif,TRUE,FALSE,FALSE,FALSE,TRUE')
    doc = parse_and_validate(content)
    assert doc.is_valid
    assert doc.rows[0].disabled is True
