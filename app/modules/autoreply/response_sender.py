from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
    User,
)

from app.modules.autoreply.constants import RESPONSE_TYPE_TEXT
from app.modules.autoreply.exceptions import AutoreplyTemplateError
from app.modules.autoreply.schemas import (
    CachedAutoreplyRule,
    MatchResult,
    SendResult,
    TemplateContext,
    TemplateUser,
)
from app.modules.autoreply.template_renderer import MsgCmdTemplateRenderer

logger = logging.getLogger(__name__)

_MEDIA_SEND_METHODS = {
    "voice": "send_voice",
    "document": "send_document",
    "photo": "send_photo",
    "video": "send_video",
    "audio": "send_audio",
    "sticker": "send_sticker",
}
_MEDIA_KWARG_NAME = {
    "voice": "voice",
    "document": "document",
    "photo": "photo",
    "video": "video",
    "audio": "audio",
    "sticker": "sticker",
}


def _to_template_user(user: User | None) -> TemplateUser | None:
    if user is None:
        return None
    return TemplateUser(
        id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        username=user.username or "",
    )


def build_template_context(message: Message, match: MatchResult) -> TemplateContext:
    replied = message.reply_to_message
    subject = _to_template_user(message.from_user) or TemplateUser(
        id=None, first_name="", last_name="", username=""
    )
    object_user: TemplateUser | None = None
    reply_text = ""
    if replied is not None:
        object_user = _to_template_user(replied.from_user) or TemplateUser(
            id=None, first_name="", last_name="", username=""
        )
        reply_text = replied.text or ""

    return TemplateContext(
        subject=subject,
        object=object_user,
        reply_text=reply_text,
        cmd_prefix=match.cmd_prefix,
        cmd_suffix=match.cmd_suffix,
        has_reply=replied is not None,
    )


def _resolve_reply_target(message: Message, rule: CachedAutoreplyRule) -> int | None:
    """Prioritas §8.7: ReplyToSender menang atas ReplyToReplied."""
    if rule.reply_to_sender:
        return message.message_id
    if rule.reply_to_replied and message.reply_to_message is not None:
        return message.reply_to_message.message_id
    return None


class AutoreplyResponseSender:
    """Memetakan `CachedAutoreplyRule` ke panggilan Telegram sungguhan
    (§13.5). `TelegramForbiddenError`/`TelegramRetryAfter` SENGAJA tidak
    ditangkap di sini -- pemanggil (`AutoreplyService`) butuh keduanya utuh
    untuk menghentikan sisa respons pada update yang sama (§22)."""

    def __init__(self, bot: Bot, renderer: MsgCmdTemplateRenderer) -> None:
        self._bot = bot
        self._renderer = renderer

    async def send(
        self, message: Message, rule: CachedAutoreplyRule, match: MatchResult
    ) -> SendResult:
        reply_target = _resolve_reply_target(message, rule)
        reply_parameters = (
            ReplyParameters(message_id=reply_target) if reply_target else None
        )

        try:
            if rule.response_type == RESPONSE_TYPE_TEXT:
                return await self._send_text(message, rule, match, reply_parameters)
            return await self._send_media(message, rule, reply_parameters)
        except AutoreplyTemplateError as exc:
            logger.warning(
                "Render template gagal, rule_id=%s source_row=%s: %s",
                rule.id,
                rule.source_row,
                exc,
            )
            return SendResult(success=False, error=str(exc))
        except TelegramBadRequest as exc:
            logger.warning(
                "TelegramBadRequest saat kirim autoreply, rule_id=%s source_row=%s: %s",
                rule.id,
                rule.source_row,
                exc,
            )
            return SendResult(success=False, error=str(exc))

    async def _send_text(
        self,
        message: Message,
        rule: CachedAutoreplyRule,
        match: MatchResult,
        reply_parameters: ReplyParameters | None,
    ) -> SendResult:
        context = build_template_context(message, match)
        rendered = self._renderer.render(rule.message_template, context)

        keyboard = None
        if rendered.buttons:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=button.label, url=button.url)]
                    for button in rendered.buttons
                ]
            )

        await self._bot.send_message(
            chat_id=message.chat.id,
            text=rendered.text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_parameters=reply_parameters,
            reply_markup=keyboard,
        )
        return SendResult(success=True)

    async def _send_media(
        self,
        message: Message,
        rule: CachedAutoreplyRule,
        reply_parameters: ReplyParameters | None,
    ) -> SendResult:
        method_name = _MEDIA_SEND_METHODS[rule.response_type]
        kwarg_name = _MEDIA_KWARG_NAME[rule.response_type]
        method = getattr(self._bot, method_name)
        await method(
            chat_id=message.chat.id,
            reply_parameters=reply_parameters,
            **{kwarg_name: rule.media_file_id},
        )
        return SendResult(success=True)
