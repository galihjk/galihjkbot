from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.methods import SendMessage


def make_telegram_exception(exc_class, **kwargs):
    method = SendMessage(chat_id=0, text="x")
    return exc_class(method, "simulated", **kwargs) if kwargs else exc_class(method, "simulated")


class FakeAutoreplyBot:
    """Bot tiruan lintas method (text + 6 tipe media) -- dipakai test
    integrasi runtime flow autoreply. `queue_reaction` mengantre respons per
    panggilan `send_*` berikutnya (None = sukses biasa)."""

    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.sent_media: list[dict] = []
        self._reactions: list[Exception | None] = []
        self._next_message_id = 1

    def queue_reaction(self, reaction: Exception | None) -> None:
        self._reactions.append(reaction)

    def _consume_reaction(self) -> Exception | None:
        if self._reactions:
            return self._reactions.pop(0)
        return None

    async def send_message(
        self,
        chat_id,
        text,
        parse_mode=None,
        disable_web_page_preview=None,
        reply_parameters=None,
        reply_markup=None,
        **kwargs,
    ):
        reaction = self._consume_reaction()
        if reaction is not None:
            raise reaction
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "reply_to_message_id": (
                    reply_parameters.message_id if reply_parameters else None
                ),
                "buttons": (
                    [
                        [(btn.text, btn.url) for btn in row]
                        for row in reply_markup.inline_keyboard
                    ]
                    if reply_markup
                    else None
                ),
            }
        )
        message_id = self._next_message_id
        self._next_message_id += 1
        return SimpleNamespace(message_id=message_id)

    async def _send_media(self, media_type, chat_id, file_id, reply_parameters=None, **kwargs):
        reaction = self._consume_reaction()
        if reaction is not None:
            raise reaction
        self.sent_media.append(
            {
                "type": media_type,
                "chat_id": chat_id,
                "file_id": file_id,
                "reply_to_message_id": (
                    reply_parameters.message_id if reply_parameters else None
                ),
            }
        )
        message_id = self._next_message_id
        self._next_message_id += 1
        return SimpleNamespace(message_id=message_id)

    async def send_voice(self, chat_id, voice, reply_parameters=None, **kwargs):
        return await self._send_media("voice", chat_id, voice, reply_parameters, **kwargs)

    async def send_document(self, chat_id, document, reply_parameters=None, **kwargs):
        return await self._send_media(
            "document", chat_id, document, reply_parameters, **kwargs
        )

    async def send_photo(self, chat_id, photo, reply_parameters=None, **kwargs):
        return await self._send_media("photo", chat_id, photo, reply_parameters, **kwargs)

    async def send_video(self, chat_id, video, reply_parameters=None, **kwargs):
        return await self._send_media("video", chat_id, video, reply_parameters, **kwargs)

    async def send_audio(self, chat_id, audio, reply_parameters=None, **kwargs):
        return await self._send_media("audio", chat_id, audio, reply_parameters, **kwargs)

    async def send_sticker(self, chat_id, sticker, reply_parameters=None, **kwargs):
        return await self._send_media(
            "sticker", chat_id, sticker, reply_parameters, **kwargs
        )


@pytest.fixture
def autoreply_bot() -> FakeAutoreplyBot:
    return FakeAutoreplyBot()
