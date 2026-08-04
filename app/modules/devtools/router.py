from __future__ import annotations

from aiogram import Router

router = Router(name="devtools")


def get_router() -> Router:
    from app.modules.devtools import handlers  # noqa: F401

    return router
