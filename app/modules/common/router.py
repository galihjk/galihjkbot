from __future__ import annotations

from aiogram import Router

router = Router(name="common")


def get_router() -> Router:
    from app.modules.common import handlers  # noqa: F401  (registers handlers)

    return router
