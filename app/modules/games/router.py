from __future__ import annotations

from aiogram import Router

router = Router(name="games")


def get_router() -> Router:
    from app.modules.games.handlers import (  # noqa: F401
        commands,
        game_callbacks,
        lobby_callbacks,
    )

    return router
