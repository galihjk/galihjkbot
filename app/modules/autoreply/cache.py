from __future__ import annotations

import asyncio

from app.modules.autoreply.schemas import AutoreplyCacheSnapshot


class AutoreplyRuleCache:
    """Snapshot immutable di memori (§17). Pembaca (`get()`) tidak pernah
    menunggu lock -- hanya `replace()` (dipanggil sync_service setelah
    commit sukses) yang butuh lock, dan itu cuma menukar referensi."""

    def __init__(self) -> None:
        self._snapshot = AutoreplyCacheSnapshot.empty()
        self._swap_lock = asyncio.Lock()

    def get(self) -> AutoreplyCacheSnapshot:
        return self._snapshot

    async def replace(self, snapshot: AutoreplyCacheSnapshot) -> None:
        async with self._swap_lock:
            self._snapshot = snapshot
