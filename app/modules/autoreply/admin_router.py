from __future__ import annotations

from aiogram import Router

router = Router(name="autoreply_admin")


def get_router() -> Router:
    from app.modules.autoreply import admin_handlers  # noqa: F401

    return router
