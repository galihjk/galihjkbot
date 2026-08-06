from __future__ import annotations

from aiogram import Router

router = Router(name="leaderboard")


def get_router() -> Router:
    from app.modules.leaderboard import handlers  # noqa: F401

    return router
