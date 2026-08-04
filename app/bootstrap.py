from __future__ import annotations

from aiogram import Dispatcher
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
from app.modules.common.router import get_router as get_common_router
from app.modules.devtools.router import get_router as get_devtools_router
from app.modules.games.engine.manager import GameManager
from app.modules.games.engine.registry import GameRegistry
from app.modules.games.implementations.simple_game.game import SimpleGame
from app.modules.games.router import get_router as get_games_router


def create_game_registry(settings: Settings) -> GameRegistry:
    registry = GameRegistry()
    # Game percobaan, sengaja tidak didaftarkan di production supaya tidak
    # muncul di /games atau bisa dipanggil lewat /game.
    if settings.app_env != "production":
        registry.register(SimpleGame())
    return registry


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
    dispatcher.include_router(get_games_router())
    dispatcher.include_router(get_devtools_router())


def build_dispatcher(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    game_registry: GameRegistry,
    game_manager: GameManager,
) -> Dispatcher:
    dispatcher = create_dispatcher()
    dispatcher.errors.register(handle_global_error)
    persona_middleware = register_middlewares(dispatcher, session_factory, settings)
    register_modules(dispatcher)
    dispatcher["game_registry"] = game_registry
    dispatcher["game_manager"] = game_manager
    dispatcher["persona_middleware"] = persona_middleware
    return dispatcher
