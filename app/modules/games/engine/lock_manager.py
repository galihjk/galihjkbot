from __future__ import annotations

import asyncio


class GameLockManager:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    def get(self, session_id: int) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def remove(self, session_id: int) -> None:
        self._locks.pop(session_id, None)
