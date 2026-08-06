from __future__ import annotations

from aiogram import F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.database.repositories import (
    audit_repository,
    autoreply_repository,
    feature_repository,
    group_repository,
)
from app.filters.admin import IsAdmin
from app.filters.private_only import PrivateOnly
from app.modules.autoreply.admin_router import router
from app.modules.autoreply.callbacks import AutoreplyCallback
from app.modules.autoreply.constants import (
    FEATURE_KEY,
    PERMISSION_EXTRACT_MEDIA_CODE,
    PERMISSION_RELOAD,
    PERMISSION_TOGGLE_GLOBAL,
    PERMISSION_TOGGLE_GROUP,
    PERMISSION_VIEW_FORMAT,
    PERMISSION_VIEW_STATUS,
    PERMISSION_VIEW_SYNC_ERRORS,
)
from app.modules.autoreply.exceptions import AutoreplySyncInProgressError
from app.modules.autoreply.keyboards import build_panel_keyboard
from app.modules.autoreply.media_code_service import MediaCodeService
from app.modules.autoreply.presenters import (
    format_panel,
    format_reload_result,
    format_sync_errors,
)
from app.modules.autoreply.sync_service import AutoreplySyncService, to_snapshot_info
from app.modules.autoreply.texts import (
    FEATURE_DISABLED_GLOBAL,
    FEATURE_ENABLED_GLOBAL,
    FORMAT_HELP_TEXT,
    GROUP_COMMAND_USAGE,
    GROUP_FEATURE_DISABLED,
    GROUP_FEATURE_ENABLED,
    GROUP_NOT_FOUND,
)

_media_code_service = MediaCodeService()


async def _render_panel(db_session: AsyncSession) -> tuple[str, bool]:
    feature = await feature_repository.get_feature(db_session, FEATURE_KEY)
    active_rule_set = await autoreply_repository.find_active_rule_set(db_session)
    snapshot = to_snapshot_info(active_rule_set) if active_rule_set is not None else None
    recent_sync = await autoreply_repository.find_recent_sync_run(db_session)
    text = format_panel(feature, snapshot, recent_sync)
    enabled = feature is not None and feature.enabled_globally
    return text, enabled


@router.message(PrivateOnly(), IsAdmin(PERMISSION_VIEW_STATUS), Command("msgcmd"))
async def handle_panel(message: Message, db_session: AsyncSession) -> None:
    text, enabled = await _render_panel(db_session)
    await message.answer(text, reply_markup=build_panel_keyboard(enabled))


@router.message(
    PrivateOnly(), IsAdmin(PERMISSION_VIEW_STATUS), Command("msgcmd_status")
)
async def handle_status(message: Message, db_session: AsyncSession) -> None:
    text, _ = await _render_panel(db_session)
    await message.answer(text)


async def _do_reload(
    db_session: AsyncSession,
    autoreply_sync_service: AutoreplySyncService,
    actor_user_id: int | None,
) -> str:
    try:
        result = await autoreply_sync_service.sync(
            db_session, triggered_by_user_id=actor_user_id, reason="manual"
        )
    except AutoreplySyncInProgressError as exc:
        return str(exc)

    active_rule_set = await autoreply_repository.find_active_rule_set(db_session)
    snapshot = to_snapshot_info(active_rule_set) if active_rule_set is not None else None
    return format_reload_result(result, snapshot)


@router.message(PrivateOnly(), IsAdmin(PERMISSION_RELOAD), Command("msgcmd_reload"))
async def handle_reload(
    message: Message,
    db_session: AsyncSession,
    current_user: User,
    autoreply_sync_service: AutoreplySyncService,
) -> None:
    text = await _do_reload(db_session, autoreply_sync_service, current_user.id)
    await message.answer(text)


@router.callback_query(
    PrivateOnly(), IsAdmin(PERMISSION_RELOAD), AutoreplyCallback.filter(F.action == "reload")
)
async def handle_reload_callback(
    callback: CallbackQuery,
    db_session: AsyncSession,
    current_user: User,
    autoreply_sync_service: AutoreplySyncService,
) -> None:
    text = await _do_reload(db_session, autoreply_sync_service, current_user.id)
    await callback.message.answer(text)
    await callback.answer()


@router.message(PrivateOnly(), IsAdmin(PERMISSION_TOGGLE_GLOBAL), Command("msgcmd_enable"))
async def handle_enable(
    message: Message, db_session: AsyncSession, current_user: User
) -> None:
    previous = await feature_repository.get_feature(db_session, FEATURE_KEY)
    await feature_repository.set_feature_enabled(db_session, FEATURE_KEY, True)
    await audit_repository.record(
        db_session,
        actor_user_id=current_user.id,
        action="autoreply.enable_global",
        entity_type="feature",
        entity_id=FEATURE_KEY,
        old_value=previous.enabled_globally if previous else None,
        new_value=True,
    )
    await message.answer(FEATURE_ENABLED_GLOBAL)


@router.message(PrivateOnly(), IsAdmin(PERMISSION_TOGGLE_GLOBAL), Command("msgcmd_disable"))
async def handle_disable(
    message: Message, db_session: AsyncSession, current_user: User
) -> None:
    previous = await feature_repository.get_feature(db_session, FEATURE_KEY)
    await feature_repository.set_feature_enabled(db_session, FEATURE_KEY, False)
    await audit_repository.record(
        db_session,
        actor_user_id=current_user.id,
        action="autoreply.disable_global",
        entity_type="feature",
        entity_id=FEATURE_KEY,
        old_value=previous.enabled_globally if previous else None,
        new_value=False,
    )
    await message.answer(FEATURE_DISABLED_GLOBAL)


@router.callback_query(
    PrivateOnly(),
    IsAdmin(PERMISSION_TOGGLE_GLOBAL),
    AutoreplyCallback.filter(F.action.in_(("enable", "disable"))),
)
async def handle_toggle_callback(
    callback: CallbackQuery,
    callback_data: AutoreplyCallback,
    db_session: AsyncSession,
    current_user: User,
) -> None:
    enable = callback_data.action == "enable"
    previous = await feature_repository.get_feature(db_session, FEATURE_KEY)
    await feature_repository.set_feature_enabled(db_session, FEATURE_KEY, enable)
    await audit_repository.record(
        db_session,
        actor_user_id=current_user.id,
        action=f"autoreply.{'enable' if enable else 'disable'}_global",
        entity_type="feature",
        entity_id=FEATURE_KEY,
        old_value=previous.enabled_globally if previous else None,
        new_value=enable,
    )
    text, enabled = await _render_panel(db_session)
    await callback.message.edit_text(text, reply_markup=build_panel_keyboard(enabled))
    await callback.answer(FEATURE_ENABLED_GLOBAL if enable else FEATURE_DISABLED_GLOBAL)


@router.message(
    PrivateOnly(), IsAdmin(PERMISSION_TOGGLE_GROUP), Command("msgcmd_group")
)
async def handle_group_toggle(
    message: Message,
    db_session: AsyncSession,
    current_user: User,
    command: CommandObject,
) -> None:
    parts = (command.args or "").split()
    if len(parts) != 2 or parts[1] not in ("on", "off"):
        await message.answer(GROUP_COMMAND_USAGE)
        return

    raw_chat_id, action = parts
    if not raw_chat_id.lstrip("-").isdigit():
        await message.answer(GROUP_COMMAND_USAGE)
        return
    chat_id = int(raw_chat_id)

    group = await group_repository.find_by_telegram_chat_id(db_session, chat_id)
    if group is None:
        await message.answer(GROUP_NOT_FOUND)
        return

    enable = action == "on"
    previous = await feature_repository.get_group_feature(db_session, group.id, FEATURE_KEY)
    await feature_repository.set_group_feature(db_session, group.id, FEATURE_KEY, enable)
    await audit_repository.record(
        db_session,
        actor_user_id=current_user.id,
        action="autoreply.toggle_group",
        entity_type="group",
        entity_id=str(chat_id),
        old_value=previous.enabled if previous else None,
        new_value=enable,
    )
    template = GROUP_FEATURE_ENABLED if enable else GROUP_FEATURE_DISABLED
    await message.answer(template.format(chat_id=chat_id))


@router.message(IsAdmin(PERMISSION_VIEW_FORMAT), Command("format_msgcmd"))
async def handle_format_help(message: Message) -> None:
    await message.answer(FORMAT_HELP_TEXT)


@router.message(
    PrivateOnly(), IsAdmin(PERMISSION_VIEW_SYNC_ERRORS), Command("msgcmd_sync_errors")
)
async def handle_sync_errors(message: Message, db_session: AsyncSession) -> None:
    sync_run = await autoreply_repository.find_recent_sync_run(db_session)
    await message.answer(format_sync_errors(sync_run))


@router.message(IsAdmin(PERMISSION_EXTRACT_MEDIA_CODE), Command("to_msgcmd"))
async def handle_to_msgcmd(message: Message) -> None:
    result = _media_code_service.extract(message.reply_to_message)
    if result.success:
        await message.answer(result.code)
    else:
        await message.answer(result.error_message)
