from __future__ import annotations

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.error_handler import handle_global_error
from app.bot.factory import create_dispatcher
from app.core.config import Settings
from app.middlewares.admin_context import AdminContextMiddleware
from app.middlewares.database import DatabaseMiddleware
from app.middlewares.group_tracking import GroupTrackingMiddleware
from app.middlewares.persona import PersonaMiddleware
from app.middlewares.user_tracking import UserTrackingMiddleware
from app.modules.admin.router import get_router as get_admin_router
from app.modules.autoreply.admin_router import get_router as get_autoreply_admin_router
from app.modules.autoreply.cache import AutoreplyRuleCache
from app.modules.autoreply.matcher import MsgCmdRuleMatcher
from app.modules.autoreply.response_sender import AutoreplyResponseSender
from app.modules.autoreply.router import get_router as get_autoreply_router
from app.modules.autoreply.service import AutoreplyService
from app.modules.autoreply.sources.google_sheet import GoogleSheetRuleSource
from app.modules.autoreply.sync_service import AutoreplySyncService
from app.modules.autoreply.template_renderer import MsgCmdTemplateRenderer
from app.modules.common.router import get_router as get_common_router
from app.modules.devtools.router import get_router as get_devtools_router
from app.modules.leaderboard.router import get_router as get_leaderboard_router
from app.modules.games.engine.manager import GameManager
from app.modules.games.engine.registry import GameRegistry
from app.modules.games.implementations.kuis_kenal.game import KuisKenalGame
from app.modules.games.implementations.kursi_kosong.game import KursiKosongGame
from app.modules.games.implementations.simple_game.game import SimpleGame
from app.modules.games.router import get_router as get_games_router


def create_game_registry(settings: Settings) -> GameRegistry:
    registry = GameRegistry()
    # Game percobaan, sengaja tidak didaftarkan di production supaya tidak
    # muncul di /games atau bisa dipanggil lewat /game.
    if settings.app_env != "production":
        registry.register(SimpleGame())
        # Kuis Kenal masih dalam pengembangan -- disembunyikan di production
        # sampai test manual Telegram (Tahap 11 rencana implementasi) selesai.
        registry.register(KuisKenalGame())
    registry.register(KursiKosongGame())
    return registry


def create_autoreply_runtime(
    settings: Settings, bot: Bot
) -> tuple[AutoreplyService, AutoreplySyncService]:
    cache = AutoreplyRuleCache()
    source = GoogleSheetRuleSource(
        settings.autoreply_source_url,
        connect_timeout_seconds=settings.autoreply_http_connect_timeout_seconds,
        read_timeout_seconds=settings.autoreply_http_read_timeout_seconds,
        max_bytes=settings.autoreply_max_source_bytes,
    )
    sync_service = AutoreplySyncService(
        source,
        cache,
        source_url=settings.autoreply_source_url,
        keep_snapshots=settings.autoreply_keep_snapshots,
    )
    sender = AutoreplyResponseSender(bot, MsgCmdTemplateRenderer())
    service = AutoreplyService(
        cache,
        MsgCmdRuleMatcher(),
        sender,
        allow_private=settings.autoreply_allow_private,
        ignore_bots=settings.autoreply_ignore_bots,
        max_responses_per_message=settings.autoreply_max_responses_per_message,
    )
    return service, sync_service


def register_middlewares(
    dispatcher: Dispatcher,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> PersonaMiddleware:
    # PersonaMiddleware harus SATU instance yang dibagi ke message & callback_query
    # (bukan dibuat ulang per observer) supaya switch persona lewat command
    # terlihat oleh klik tombol juga -- middleware lain stateless jadi aman
    # dibuat ulang per observer.
    persona_middleware = PersonaMiddleware(settings.telegram_superadmin_ids)

    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(DatabaseMiddleware(session_factory))
        observer.outer_middleware(UserTrackingMiddleware())
        observer.outer_middleware(persona_middleware)
        observer.outer_middleware(
            AdminContextMiddleware(settings.telegram_superadmin_ids)
        )
        observer.outer_middleware(GroupTrackingMiddleware())

    return persona_middleware


def register_modules(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(get_common_router())
    dispatcher.include_router(get_admin_router())
    # devtools SEBELUM games: /p0../p7 (persona switch) harus dapat giliran
    # cek lebih dulu daripada handler pesan privat generik milik games
    # (`handle_private_game_message`), yang menangkap SEMUA pesan privat
    # (termasuk command) selama pengirim punya konteks input privat aktif --
    # kalau urutannya kebalik, admin yang sedang berperan sebagai virtual
    # player dengan konteks jawab/nilai aktif tidak akan pernah bisa ketik
    # /pN buat ganti persona (perintahnya keburu "ditelan" game). Diuji di
    # tests/modules/devtools/test_persona_routing.py.
    dispatcher.include_router(get_devtools_router())
    dispatcher.include_router(get_games_router())
    dispatcher.include_router(get_leaderboard_router())
    dispatcher.include_router(get_autoreply_admin_router())
    # Fallback terakhir -- lihat §19 desain: tidak boleh mengambil update
    # yang seharusnya diproses command/game router di atas.
    dispatcher.include_router(get_autoreply_router())


def build_dispatcher(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    game_registry: GameRegistry,
    game_manager: GameManager,
    autoreply_service: AutoreplyService,
    autoreply_sync_service: AutoreplySyncService,
) -> Dispatcher:
    dispatcher = create_dispatcher()
    dispatcher.errors.register(handle_global_error)
    persona_middleware = register_middlewares(dispatcher, session_factory, settings)
    register_modules(dispatcher)
    dispatcher["game_registry"] = game_registry
    dispatcher["game_manager"] = game_manager
    dispatcher["persona_middleware"] = persona_middleware
    dispatcher["autoreply_service"] = autoreply_service
    dispatcher["autoreply_sync_service"] = autoreply_sync_service
    return dispatcher
