from __future__ import annotations

from types import SimpleNamespace

from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from app.core.enums import AdminRole
from app.database.repositories import feature_repository, group_repository
from app.modules.autoreply.cache import AutoreplyRuleCache
from app.modules.autoreply.matcher import MsgCmdRuleMatcher, normalize_for_match
from app.modules.autoreply.response_sender import AutoreplyResponseSender
from app.modules.autoreply.schemas import AutoreplyCacheSnapshot, CachedAutoreplyRule
from app.modules.autoreply.service import AutoreplyService
from app.modules.autoreply.template_renderer import MsgCmdTemplateRenderer
from tests.modules.autoreply.conftest import make_telegram_exception


def _rule(
    id_: int,
    command: str,
    template: str,
    *,
    response_type: str = "text",
    media_file_id: str | None = None,
    match_all: bool = True,
    reply_to_sender: bool = True,
    reply_to_replied: bool = False,
    admin_only: bool = False,
) -> CachedAutoreplyRule:
    return CachedAutoreplyRule(
        id=id_,
        rule_set_id=1,
        source_row=id_,
        command=command,
        normalized_command=normalize_for_match(command),
        message_template=template,
        response_type=response_type,
        media_file_id=media_file_id,
        match_all=match_all,
        reply_to_sender=reply_to_sender,
        reply_to_replied=reply_to_replied,
        admin_only=admin_only,
    )


def _message(
    *,
    text: str,
    chat_id: int = 100,
    chat_type: str = ChatType.GROUP,
    message_id: int = 1,
    user_id: int = 1,
    is_bot: bool = False,
    reply_to_message=None,
):
    return SimpleNamespace(
        text=text,
        message_id=message_id,
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        from_user=SimpleNamespace(
            id=user_id, first_name="Budi", last_name="", username="budi", is_bot=is_bot
        ),
        reply_to_message=reply_to_message,
    )


def _replied(*, text: str, message_id: int = 50, user_id: int = 2):
    return SimpleNamespace(
        text=text,
        message_id=message_id,
        from_user=SimpleNamespace(
            id=user_id, first_name="Rani", last_name="", username="", is_bot=False
        ),
    )


def _build_service(bot, *, allow_private=False, ignore_bots=True, max_responses=20):
    cache = AutoreplyRuleCache()
    matcher = MsgCmdRuleMatcher()
    sender = AutoreplyResponseSender(bot, MsgCmdTemplateRenderer())
    service = AutoreplyService(
        cache,
        matcher,
        sender,
        allow_private=allow_private,
        ignore_bots=ignore_bots,
        max_responses_per_message=max_responses,
    )
    return service, cache


async def _enable_feature(session_factory, group_id: int | None = None) -> None:
    async with session_factory() as db_session:
        await feature_repository.set_feature_enabled(db_session, "autoreply", True)
        await db_session.commit()


async def test_feature_disabled_globally_skips(session_factory, autoreply_bot):
    service, cache = _build_service(autoreply_bot)
    cache.get  # no-op, snapshot stays empty by default but populate anyway
    async with session_factory() as db_session:
        await feature_repository.set_feature_enabled(db_session, "autoreply", False)
        await db_session.commit()

        result = await service.handle_message(
            _message(text="halo"), db_session, None, None
        )
    assert result.status == "skipped"
    assert result.reason == "feature_disabled"
    assert autoreply_bot.sent_messages == []


async def test_group_override_disables_even_when_global_on(session_factory, autoreply_bot):
    service, cache = _build_service(autoreply_bot)
    async with session_factory() as db_session:
        await feature_repository.set_feature_enabled(db_session, "autoreply", True)
        group = await group_repository.upsert_group(
            db_session, SimpleNamespace(id=999, title="G", username=None, type="group")
        )
        await feature_repository.set_group_feature(db_session, group.id, "autoreply", False)
        await db_session.commit()

        result = await service.handle_message(
            _message(text="halo"), db_session, group, None
        )
    assert result.status == "skipped"
    assert result.reason == "feature_disabled"


async def test_match_renders_and_sends_reply_to_sender(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule = _rule(1, "halo", "Halo, (sbj_dpn)!")
    await cache.replace(
        AutoreplyCacheSnapshot(rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule,))
    )

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="halo", message_id=7), db_session, None, None
        )

    assert result.status == "processed"
    assert result.sent_rules_count == 1
    assert autoreply_bot.sent_messages[0]["text"] == "Halo, Budi!"
    assert autoreply_bot.sent_messages[0]["reply_to_message_id"] == 7


async def test_admin_only_rule_requires_permission(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule = _rule(1, "admin test", "Perintah admin oleh (sbj).", admin_only=True)
    await cache.replace(
        AutoreplyCacheSnapshot(rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule,))
    )

    async with session_factory() as db_session:
        no_perm = await service.handle_message(
            _message(text="admin test"), db_session, None, None
        )
    assert no_perm.sent_rules_count == 0
    assert autoreply_bot.sent_messages == []

    async with session_factory() as db_session:
        with_perm = await service.handle_message(
            _message(text="admin test"), db_session, None, AdminRole.OPERATOR
        )
    assert with_perm.sent_rules_count == 1


async def test_bot_sender_ignored(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule = _rule(1, "halo", "Halo!")
    await cache.replace(
        AutoreplyCacheSnapshot(rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule,))
    )

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="halo", is_bot=True), db_session, None, None
        )
    assert result.status == "skipped"
    assert result.reason == "bot_sender"


async def test_media_rule_sends_via_correct_method(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule = _rule(
        1, "suara", "*voice:AAA", response_type="voice", media_file_id="AAA"
    )
    await cache.replace(
        AutoreplyCacheSnapshot(rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule,))
    )

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="suara", message_id=3), db_session, None, None
        )

    assert result.sent_rules_count == 1
    assert autoreply_bot.sent_media[0] == {
        "type": "voice",
        "chat_id": 100,
        "file_id": "AAA",
        "reply_to_message_id": 3,
    }


async def test_multiple_matches_sent_in_source_row_order(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule_a = _rule(1, "halo", "Pertama", reply_to_sender=False)
    rule_b = _rule(2, "halo", "Kedua", reply_to_sender=False)
    await cache.replace(
        AutoreplyCacheSnapshot(
            rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule_a, rule_b)
        )
    )

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="halo"), db_session, None, None
        )

    assert result.sent_rules_count == 2
    assert [m["text"] for m in autoreply_bot.sent_messages] == ["Pertama", "Kedua"]


async def test_bad_request_on_one_rule_does_not_block_others(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule_a = _rule(1, "halo", "Pertama", reply_to_sender=False)
    rule_b = _rule(2, "halo", "Kedua", reply_to_sender=False)
    await cache.replace(
        AutoreplyCacheSnapshot(
            rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule_a, rule_b)
        )
    )
    autoreply_bot.queue_reaction(make_telegram_exception(TelegramBadRequest))

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="halo"), db_session, None, None
        )

    assert result.matched_rules_count == 2
    assert result.sent_rules_count == 1
    assert autoreply_bot.sent_messages[0]["text"] == "Kedua"


async def test_retry_after_stops_remaining_responses(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule_a = _rule(1, "halo", "Pertama", reply_to_sender=False)
    rule_b = _rule(2, "halo", "Kedua", reply_to_sender=False)
    await cache.replace(
        AutoreplyCacheSnapshot(
            rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule_a, rule_b)
        )
    )
    autoreply_bot.queue_reaction(
        make_telegram_exception(TelegramRetryAfter, retry_after=5)
    )

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="halo"), db_session, None, None
        )

    assert result.sent_rules_count == 0
    assert autoreply_bot.sent_messages == []


async def test_max_responses_per_message_cap(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot, max_responses=1)
    rule_a = _rule(1, "halo", "Pertama", reply_to_sender=False)
    rule_b = _rule(2, "halo", "Kedua", reply_to_sender=False)
    await cache.replace(
        AutoreplyCacheSnapshot(
            rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule_a, rule_b)
        )
    )

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="halo"), db_session, None, None
        )

    assert result.matched_rules_count == 2
    assert result.sent_rules_count == 1
    assert len(autoreply_bot.sent_messages) == 1


async def test_reply_to_replied_used_when_sender_flag_false(session_factory, autoreply_bot):
    await _enable_feature(session_factory)
    service, cache = _build_service(autoreply_bot)
    rule = _rule(
        1, "halo", "(isreply)balas @obj((obj_dpn))@(/isreply)",
        reply_to_sender=False, reply_to_replied=True,
    )
    await cache.replace(
        AutoreplyCacheSnapshot(rule_set_id=1, public_id="ARS-000001", checksum="x", activated_at=None, rules=(rule,))
    )
    replied = _replied(text="pesan lama", message_id=42)

    async with session_factory() as db_session:
        result = await service.handle_message(
            _message(text="halo", reply_to_message=replied), db_session, None, None
        )

    assert result.sent_rules_count == 1
    sent = autoreply_bot.sent_messages[0]
    assert sent["reply_to_message_id"] == 42
    assert sent["text"] == 'balas <a href="tg://user?id=2">Rani</a>'
