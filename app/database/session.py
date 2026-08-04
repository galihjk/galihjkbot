from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.database.sqlite import register_sqlite_pragmas


def create_engine(settings: Settings) -> AsyncEngine:
    engine = create_async_engine(settings.database_url)
    register_sqlite_pragmas(engine)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
