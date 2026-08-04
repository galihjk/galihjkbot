from __future__ import annotations

from aiogram import Router

router = Router(name="admin")


def get_router() -> Router:
    from app.modules.admin.handlers import (  # noqa: F401
        dashboard,
        groups,
        health,
        users,
    )

    return router
