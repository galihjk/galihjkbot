from __future__ import annotations

from types import SimpleNamespace

from app.modules.autoreply.media_code_service import MediaCodeService

service = MediaCodeService()


def _media(text=None, **kwargs):
    defaults = dict(
        text=text, voice=None, document=None, photo=None, video=None, audio=None, sticker=None
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_no_reply_returns_error():
    result = service.extract(None)
    assert result.success is False
    assert "Balas sebuah" in result.error_message


def test_text_reply_returns_error():
    result = service.extract(_media(text="halo"))
    assert result.success is False
    assert "media non-teks" in result.error_message


def test_voice_extracted_with_prefix():
    result = service.extract(_media(voice=SimpleNamespace(file_id="V1")))
    assert result.success is True
    assert result.code == "*voice:V1"


def test_document_extracted_with_prefix():
    result = service.extract(_media(document=SimpleNamespace(file_id="D1")))
    assert result.code == "*document:D1"


def test_photo_picks_largest_by_area():
    small = SimpleNamespace(file_id="small", width=100, height=100, file_size=1000)
    large = SimpleNamespace(file_id="large", width=800, height=800, file_size=50000)
    result = service.extract(_media(photo=[small, large]))
    assert result.code == "*photo:large"


def test_video_audio_sticker_prefixes():
    assert service.extract(_media(video=SimpleNamespace(file_id="V"))).code == "*video:V"
    assert service.extract(_media(audio=SimpleNamespace(file_id="A"))).code == "*audio:A"
    assert service.extract(_media(sticker=SimpleNamespace(file_id="S"))).code == "*sticker:S"


def test_unsupported_media_type_returns_error():
    result = service.extract(_media())
    assert result.success is False
    assert "tidak didukung" in result.error_message
