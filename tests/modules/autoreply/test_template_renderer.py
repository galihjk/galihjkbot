from __future__ import annotations

import pytest

from app.modules.autoreply.exceptions import AutoreplyTemplateError
from app.modules.autoreply.schemas import TemplateContext, TemplateUser
from app.modules.autoreply.template_renderer import (
    MsgCmdTemplateRenderer,
    validate_template_structure,
)

renderer = MsgCmdTemplateRenderer()


def _ctx(**overrides) -> TemplateContext:
    defaults = dict(
        subject=TemplateUser(id=1, first_name="Budi", last_name="Santoso", username="budi"),
        object=None,
        reply_text="",
        cmd_prefix="",
        cmd_suffix="",
        has_reply=False,
    )
    defaults.update(overrides)
    return TemplateContext(**defaults)


def test_subject_placeholders():
    result = renderer.render("(sbj_dpn)/(sbj_blk)/(sbj_un)/(sbj_id)/(sbj)", _ctx())
    assert result.text == "Budi/Santoso/budi/1/Budi Santoso"


def test_object_placeholders_empty_when_no_object():
    result = renderer.render("(obj_dpn)|(obj_un)|(obj_id)|(obj)", _ctx())
    assert result.text == "|||"


def test_object_placeholders_filled_when_present():
    ctx = _ctx(
        object=TemplateUser(id=2, first_name="Rani", last_name="", username=""),
        has_reply=True,
    )
    result = renderer.render("(obj_dpn)/(obj_id)", ctx)
    assert result.text == "Rani/2"


def test_reply_text_placeholder():
    ctx = _ctx(reply_text="pesan lama", has_reply=True)
    result = renderer.render("(rep_txt)", ctx)
    assert result.text == "pesan lama"


def test_command_prefix_suffix_placeholders():
    ctx = _ctx(cmd_prefix="Rani ", cmd_suffix=" Budi")
    result = renderer.render("(cmd_dpn)|(cmd_ket)", ctx)
    assert result.text == "Rani | Budi"


def test_isreply_isnotreply_pair():
    template = "(isreply)ada balasan(/isreply)(isnotreply)tidak ada(/isnotreply)"
    assert renderer.render(template, _ctx(has_reply=True)).text == "ada balasan"
    assert renderer.render(template, _ctx(has_reply=False)).text == "tidak ada"


def test_obj_equal_sbj_pair():
    template = "(obj=sbj)sama(/obj=sbj)(obj!=sbj)beda(/obj!=sbj)"
    same_user = TemplateUser(id=1, first_name="Budi", last_name="", username="")
    assert renderer.render(template, _ctx(object=same_user)).text == "sama"

    other_user = TemplateUser(id=2, first_name="Rani", last_name="", username="")
    assert renderer.render(template, _ctx(object=other_user)).text == "beda"

    # Object tidak ada -> dianggap berbeda (§10.6).
    assert renderer.render(template, _ctx(object=None)).text == "beda"


def test_obj_equal_sbj_as_text_shorthand():
    same_user = TemplateUser(id=1, first_name="Budi", last_name="", username="")
    result = renderer.render("(obj=sbj_as_dirinya sendiri)", _ctx(object=same_user))
    assert result.text == "dirinya sendiri"

    other_user = TemplateUser(id=2, first_name="Rani", last_name="", username="")
    result = renderer.render("(obj=sbj_as_dirinya sendiri)", _ctx(object=other_user))
    assert result.text == ""


def test_command_existence_conditions():
    template = "(ada_ket)ada ket(/ada_ket)(tdk_ada_ket)tidak ada ket(/tdk_ada_ket)"
    assert renderer.render(template, _ctx(cmd_suffix=" halo")).text == "ada ket"
    assert renderer.render(template, _ctx(cmd_suffix="")).text == "tidak ada ket"


def test_username_existence_conditions():
    template = "(ada_sbj_un)ada(/ada_sbj_un)(tdk_ada_sbj_un)tidak(/tdk_ada_sbj_un)"
    with_username = _ctx(
        subject=TemplateUser(id=1, first_name="Budi", last_name="", username="budi")
    )
    without_username = _ctx(
        subject=TemplateUser(id=1, first_name="Budi", last_name="", username="")
    )
    assert renderer.render(template, with_username).text == "ada"
    assert renderer.render(template, without_username).text == "tidak"


def test_reply_text_existence_conditions():
    template = "(ada_rep_txt)ada(/ada_rep_txt)(tdk_ada_rep_txt)tidak(/tdk_ada_rep_txt)"
    assert renderer.render(template, _ctx(reply_text="halo", has_reply=True)).text == "ada"
    assert renderer.render(template, _ctx(reply_text="", has_reply=True)).text == "tidak"


def test_mention_subject_and_empty_object_mention():
    result = renderer.render("@sbj((sbj_dpn))@ dan @obj((obj_dpn))@", _ctx())
    assert result.text == '<a href="tg://user?id=1">Budi</a> dan '


def test_mention_object_when_present():
    ctx = _ctx(object=TemplateUser(id=9, first_name="Sari", last_name="", username=""))
    result = renderer.render("@obj((obj_dpn))@", ctx)
    assert result.text == '<a href="tg://user?id=9">Sari</a>'


def test_html_escape_on_dynamic_values():
    ctx = _ctx(
        subject=TemplateUser(id=1, first_name="<b>Budi</b>", last_name="", username="")
    )
    result = renderer.render("(sbj_dpn)", ctx)
    assert result.text == "&lt;b&gt;Budi&lt;/b&gt;"


def test_admin_written_markup_is_preserved():
    result = renderer.render("<b>Aturan grup</b>", _ctx())
    assert result.text == "<b>Aturan grup</b>"


def test_single_button_extracted():
    result = renderer.render(
        "<b>Info</b>\n(btn=https://example.com)Buka Situs(/btn)", _ctx()
    )
    assert result.text == "<b>Info</b>\n"
    assert result.buttons[0].label == "Buka Situs"
    assert result.buttons[0].url == "https://example.com"


def test_button_without_scheme_defaults_to_http():
    result = renderer.render(
        "<b>Info</b>\n(btn=t.me/galihjkdev)Buka Situs(/btn)", _ctx()
    )
    assert result.buttons[0].url == "http://t.me/galihjkdev"


def test_multiple_buttons_preserve_order():
    template = (
        "(btn=https://a.example)A(/btn)"
        "(btn=https://b.example)B(/btn)"
    )
    result = renderer.render(template, _ctx())
    assert [b.label for b in result.buttons] == ["A", "B"]
    assert [b.url for b in result.buttons] == ["https://a.example", "https://b.example"]


def test_render_handles_contained_different_tag_types_correctly():
    # End-to-end untuk pola resmi Lampiran B.4: (obj!=sbj) di dalam
    # (isreply) harus benar-benar RENDER dengan benar, tidak cuma lolos
    # validasi struktur.
    template = (
        "(isreply)(sbj_dpn) memilih "
        "(obj=sbj_as_dirinya sendiri)(obj!=sbj)(obj_dpn)(/obj!=sbj).(/isreply)"
    )
    same_user = TemplateUser(id=1, first_name="Budi", last_name="", username="")
    result = renderer.render(template, _ctx(object=same_user, has_reply=True))
    assert result.text == "Budi memilih dirinya sendiri."

    other_user = TemplateUser(id=2, first_name="Rani", last_name="", username="")
    result = renderer.render(template, _ctx(object=other_user, has_reply=True))
    assert result.text == "Budi memilih Rani."


def test_output_too_long_raises():
    with pytest.raises(AutoreplyTemplateError):
        renderer.render("x" * 5000, _ctx())


# --- validate_template_structure (statis, dipanggil saat sync) ---


def test_validate_balanced_tags_ok():
    template = "(isreply)a(/isreply)(isnotreply)b(/isnotreply)"
    assert validate_template_structure(template) == []


def test_validate_detects_unbalanced_tag():
    template = "(isreply)a(/isnotreply)"
    errors = validate_template_structure(template)
    assert any("tidak seimbang" in e for e in errors)


def test_validate_detects_same_tag_nested_in_itself():
    # (isreply) di dalam (isreply) lain -- ini yang benar-benar merusak
    # regex non-greedy per pass (§10.11), BUKAN tag beda jenis yang saling
    # mengandung.
    template = "(isreply)a(isreply)b(/isreply)c(/isreply)"
    errors = validate_template_structure(template)
    assert any("bersarang" in e for e in errors)


def test_validate_allows_different_tag_types_contained_within_each_other():
    # Pola resmi Lampiran B.4 desain: (obj!=sbj) sepenuhnya di dalam
    # (isreply) -- ini BUKAN nesting yang dilarang, karena tiap jenis tag
    # diproses lewat pass regex sendiri yang independen.
    template = (
        "(isreply)(sbj_dpn) memilih "
        "(obj=sbj_as_dirinya sendiri)(obj!=sbj)(obj_dpn)(/obj!=sbj).(/isreply)"
    )
    assert validate_template_structure(template) == []


def test_validate_allows_sequential_same_tag_pairs():
    # Dua pasang (ada_ket)...(/ada_ket) yang SIBLING (berurutan, tidak
    # bersarang) -- pola nyata dari Sheet produksi (cabang isreply/
    # isnotreply masing-masing punya blok ada_ket/tdk_ada_ket sendiri).
    template = (
        "(isreply)(ada_ket)a(/ada_ket)(tdk_ada_ket)b(/tdk_ada_ket)(/isreply)"
        "(isnotreply)(ada_ket)c(/ada_ket)(tdk_ada_ket)d(/tdk_ada_ket)(/isnotreply)"
    )
    assert validate_template_structure(template) == []


def test_validate_button_url_scheme():
    template = "(btn=ftp://example.com)Label(/btn)teks"
    errors = validate_template_structure(template)
    assert any("harus berskema" in e for e in errors)


def test_validate_button_without_scheme_defaults_to_http_and_passes():
    # §10.10 (diubah): URL tanpa scheme sama sekali otomatis dianggap
    # http, BUKAN error -- admin Sheet tidak perlu ingat menulis https://.
    template = "Halo (btn=t.me/galihjkdev)lihat channel(/btn)"
    assert validate_template_structure(template) == []


def test_validate_button_label_not_empty():
    template = "(btn=https://example.com)(/btn)teks"
    errors = validate_template_structure(template)
    assert any("Label tombol tidak boleh kosong" in e for e in errors)


def test_validate_rejects_button_only_rule():
    template = "(btn=https://example.com)Buka(/btn)"
    errors = validate_template_structure(template)
    assert any("tidak boleh kosong" in e for e in errors)


def test_validate_allows_text_alongside_button():
    template = "Halo dunia (btn=https://example.com)Buka(/btn)"
    assert validate_template_structure(template) == []
