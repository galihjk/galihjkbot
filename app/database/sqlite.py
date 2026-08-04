from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine


def register_sqlite_pragmas(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.close()
