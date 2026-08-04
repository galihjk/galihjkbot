from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameResult:
    winner_user_id: int | None
    summary: str
    payload: dict | None = None
