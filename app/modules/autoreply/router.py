from __future__ import annotations

from aiogram import Router

router = Router(name="autoreply")


def get_router() -> Router:
    from app.modules.autoreply import handlers  # noqa: F401

    return router
