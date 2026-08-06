from __future__ import annotations

from aiogram import Router

router = Router(name="games")


def get_router() -> Router:
    from app.modules.games.handlers import (  # noqa: F401
        commands,
        game_callbacks,
        howtoplay,
        lobby_callbacks,
        private_game_messages,
    )

    return router
