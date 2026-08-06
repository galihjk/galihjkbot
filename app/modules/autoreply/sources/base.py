from __future__ import annotations

from typing import Protocol

from app.modules.autoreply.schemas import RawSource


class RuleSource(Protocol):
    async def fetch(self) -> RawSource: ...
