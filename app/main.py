from __future__ import annotations

import asyncio
import logging

from app.bootstrap import build_dispatcher, create_game_registry
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

    dispatcher = build_dispatcher(session_factory, settings, game_registry, game_manager)
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
            await _notify_superadmins_startup(bot, settings)
            await dispatcher.start_polling(bot)
    finally:
        leaderboard_task.cancel()
        await engine.dispose()


async def _notify_superadmins_startup(bot, settings) -> None:  # noqa: ANN001
    text = f"🟢 {settings.app_name} v{settings.app_version} ({settings.app_env}) aktif."
    for superadmin_id in settings.telegram_superadmin_ids:
        try:
            await bot.send_message(superadmin_id, text)
        except Exception:
            logger.exception("Gagal mengirim notifikasi startup ke %s", superadmin_id)


if __name__ == "__main__":
    asyncio.run(main())
