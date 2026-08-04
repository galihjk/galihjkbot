from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameMetadata:
    key: str
    name: str
    description: str
    min_players: int
    max_players: int
    lobby_timeout_seconds: int
    ready_check_seconds: int
    supports_restore: bool = False
    enabled: bool = True
