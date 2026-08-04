from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class TimerRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def register(self, key: str, task: asyncio.Task) -> None:
        self.cancel(key)
        self._tasks[key] = task

    def schedule(
        self,
        key: str,
        delay_seconds: float,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        async def _runner() -> None:
            try:
                await asyncio.sleep(max(delay_seconds, 0))
                await callback()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Timer '%s' gagal dieksekusi", key)

        self.register(key, asyncio.create_task(_runner()))

    def cancel(self, key: str) -> None:
        task = self._tasks.pop(key, None)
        if task is None or task.done():
            return
        if task is asyncio.current_task():
            # Timer yang sedang berjalan memicu pembersihan dirinya sendiri
            # (misal handle_timeout -> cancel_game -> cancel_session). Jangan
            # di-cancel di sini, atau eksekusinya sendiri terputus sebelum
            # selesai commit -- cukup lepas dari tracking, biarkan selesai
            # secara normal.
            return
        task.cancel()

    def cancel_session(self, session_id: int) -> None:
        kinds = ("lobby", "starting", "turn", "game")
        for key in list(self._tasks):
            kind, _, sid = key.partition(":")
            if kind in kinds and sid == str(session_id):
                self.cancel(key)
