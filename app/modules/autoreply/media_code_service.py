from __future__ import annotations

from aiogram.types import Message

from app.modules.autoreply.constants import MEDIA_PREFIXES
from app.modules.autoreply.schemas import MediaCodeResult
from app.modules.autoreply.texts import TO_MSGCMD_NO_REPLY

_RESPONSE_TYPE_TO_PREFIX = {response_type: prefix for prefix, response_type in MEDIA_PREFIXES.items()}


class MediaCodeService:
    """`/to_msgcmd` (§21.5, §13 -- ekstraksi `file_id` dari media yang
    dibalas, diformat siap tempel ke kolom `Message` di Sheet."""

    def extract(self, replied_message: Message | None) -> MediaCodeResult:
        if replied_message is None:
            return MediaCodeResult(success=False, error_message=TO_MSGCMD_NO_REPLY)

        if replied_message.text is not None:
            return MediaCodeResult(
                success=False,
                error_message="Pesan yang dibalas harus berupa media non-teks.",
            )

        if replied_message.voice is not None:
            return self._ok("voice", replied_message.voice.file_id)
        if replied_message.document is not None:
            return self._ok("document", replied_message.document.file_id)
        if replied_message.photo:
            largest = max(
                replied_message.photo,
                key=lambda size: (size.file_size or 0, size.width * size.height),
            )
            return self._ok("photo", largest.file_id)
        if replied_message.video is not None:
            return self._ok("video", replied_message.video.file_id)
        if replied_message.audio is not None:
            return self._ok("audio", replied_message.audio.file_id)
        if replied_message.sticker is not None:
            return self._ok("sticker", replied_message.sticker.file_id)

        return MediaCodeResult(
            success=False,
            error_message="Tipe media pesan ini tidak didukung MsgCmd.",
        )

    def _ok(self, response_type: str, file_id: str) -> MediaCodeResult:
        prefix = _RESPONSE_TYPE_TO_PREFIX[response_type]
        return MediaCodeResult(success=True, code=f"{prefix}{file_id}")
