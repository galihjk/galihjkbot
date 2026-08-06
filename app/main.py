from __future__ import annotations

import asyncio
import logging

from app.bootstrap import build_dispatcher, create_autoreply_runtime, create_game_registry
from app.bot.factory import create_bot
from app.core.config import BASE_DIR, get_settings
from app.core.logging import setup_logging
from app.database.session import create_engine, create_session_factory
from app.modules.games.engine.manager import GameManager
from app.modules.leaderboard.scheduler import run_forever as run_leaderboard_scheduler
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, BASE_DIR / "logs")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    bot = create_bot(settings)
    game_registry = create_game_registry(settings)
    game_manager = GameManager(game_registry, session_factory, bot)
    autoreply_service, autoreply_sync_service = create_autoreply_runtime(settings, bot)

    dispatcher = build_dispatcher(
        session_factory,
        settings,
        game_registry,
        game_manager,
        autoreply_service,
        autoreply_sync_service,
    )
    dispatcher["settings"] = settings
    dispatcher["started_at"] = utcnow()

    logger.info(
        "Starting %s v%s (%s)",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )

    leaderboard_task = asyncio.create_task(
        run_leaderboard_scheduler(bot, session_factory, settings)
    )
    try:
        async with bot:
            await bot.delete_webhook(
                drop_pending_updates=settings.telegram_drop_pending_updates
            )
            await game_manager.recover_sessions()
            autoreply_status = await _startup_autoreply(
                session_factory, autoreply_sync_service, settings
            )
            await _notify_superadmins_startup(bot, settings, autoreply_status)
            await dispatcher.start_polling(bot)
    finally:
        leaderboard_task.cancel()
        await engine.dispose()


async def _startup_autoreply(
    session_factory, autoreply_sync_service, settings
) -> str:  # noqa: ANN001
    """§16.3: muat snapshot aktif dari SQLite (tanpa network), lalu (opsional)
    coba sync sekali. Kegagalan sync TIDAK PERNAH mencegah bot polling --
    snapshot cache lama (kalau ada) tetap dipakai (last-known-good)."""
    async with session_factory() as db_session:
        info = await autoreply_sync_service.load_active_snapshot(db_session)

    status = "READY_CACHED" if info is not None else "DEGRADED_EMPTY"

    if settings.autoreply_startup_sync and settings.autoreply_source_url:
        async with session_factory() as db_session:
            try:
                result = await autoreply_sync_service.sync(
                    db_session, triggered_by_user_id=None, reason="startup"
                )
            except Exception:
                logger.exception("Startup sync autoreply gagal tak terduga.")
                status = "DEGRADED_CACHED" if info is not None else "DEGRADED_EMPTY"
            else:
                if result.status in ("success", "unchanged"):
                    status = "READY_CACHED"
                else:
                    status = "DEGRADED_CACHED" if info is not None else "DEGRADED_EMPTY"

    logger.info("Autoreply startup selesai. status=%s", status)
    return status


async def _notify_superadmins_startup(
    bot, settings, autoreply_status: str = "UNKNOWN"
) -> None:  # noqa: ANN001
    text = (
        f"🟢 {settings.app_name} v{settings.app_version} ({settings.app_env}) aktif.\n"
        f"Autoreply: {autoreply_status}"
    )
    for superadmin_id in settings.telegram_superadmin_ids:
        try:
            await bot.send_message(superadmin_id, text)
        except Exception:
            logger.exception("Gagal mengirim notifikasi startup ke %s", superadmin_id)


if __name__ == "__main__":
    asyncio.run(main())
