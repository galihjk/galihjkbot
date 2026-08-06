from __future__ import annotations

import logging

from aiogram.enums import ChatType
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.database.models.group import Group
from app.modules.autoreply.cache import AutoreplyRuleCache
from app.modules.autoreply.constants import (
    ALLOWED_CHAT_TYPES_GROUP,
    FEATURE_KEY,
    PERMISSION_TRIGGER_ADMIN_RULE,
)
from app.modules.autoreply.matcher import MsgCmdRuleMatcher
from app.modules.autoreply.response_sender import AutoreplyResponseSender
from app.modules.autoreply.schemas import (
    AutoreplyExecutionResult,
    CachedAutoreplyRule,
    MatchResult,
)
from app.services import feature_service
from app.services.permission_service import has_minimum_role

logger = logging.getLogger(__name__)


class AutoreplyService:
    """Orkestrasi runtime (§13.2, Lampiran C). Satu instance dibagi lintas
    request, stateless kecuali lewat `cache` yang diinject."""

    def __init__(
        self,
        cache: AutoreplyRuleCache,
        matcher: MsgCmdRuleMatcher,
        sender: AutoreplyResponseSender,
        *,
        allow_private: bool,
        ignore_bots: bool,
        max_responses_per_message: int,
    ) -> None:
        self._cache = cache
        self._matcher = matcher
        self._sender = sender
        self._allow_private = allow_private
        self._ignore_bots = ignore_bots
        self._max_responses_per_message = max_responses_per_message

    async def handle_message(
        self,
        message: Message,
        db_session: AsyncSession,
        current_group: Group | None,
        admin_role: AdminRole | None,
    ) -> AutoreplyExecutionResult:
        if message.text is None:
            return AutoreplyExecutionResult.skipped("no_text")

        if (
            self._ignore_bots
            and message.from_user is not None
            and message.from_user.is_bot
        ):
            return AutoreplyExecutionResult.skipped("bot_sender")

        chat_type = message.chat.type
        if chat_type == ChatType.PRIVATE:
            if not self._allow_private:
                return AutoreplyExecutionResult.skipped("private_not_allowed")
        elif chat_type not in ALLOWED_CHAT_TYPES_GROUP:
            return AutoreplyExecutionResult.skipped("unsupported_chat_type")

        if not await feature_service.is_enabled(db_session, FEATURE_KEY, current_group):
            return AutoreplyExecutionResult.skipped("feature_disabled")

        snapshot = self._cache.get()
        if snapshot.is_empty:
            return AutoreplyExecutionResult.skipped("no_snapshot")

        candidates: list[tuple[CachedAutoreplyRule, MatchResult]] = []
        for rule in snapshot.rules:
            if rule.admin_only and not has_minimum_role(
                admin_role, PERMISSION_TRIGGER_ADMIN_RULE
            ):
                continue
            match = self._matcher.match(rule, message.text)
            if match.matched:
                candidates.append((rule, match))

        if len(candidates) > self._max_responses_per_message:
            logger.warning(
                "Jumlah rule cocok (%s) melebihi batas %s, sisanya dilewati.",
                len(candidates),
                self._max_responses_per_message,
            )

        sent_count = 0
        for rule, match in candidates[: self._max_responses_per_message]:
            try:
                result = await self._sender.send(message, rule, match)
            except TelegramRetryAfter:
                logger.warning(
                    "TelegramRetryAfter -- hentikan sisa respons autoreply utk update ini."
                )
                break
            except TelegramForbiddenError:
                logger.warning(
                    "TelegramForbiddenError -- hentikan respons autoreply utk update ini."
                )
                break
            except Exception:
                logger.exception(
                    "Error tak terduga saat kirim autoreply, rule_id=%s source_row=%s",
                    rule.id,
                    rule.source_row,
                )
                continue

            if result.success:
                sent_count += 1
            else:
                logger.warning(
                    "Autoreply gagal terkirim, rule_id=%s source_row=%s",
                    rule.id,
                    rule.source_row,
                )

        return AutoreplyExecutionResult.from_counts(len(candidates), sent_count)
