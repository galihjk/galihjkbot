from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.modules.games.engine.context import GameContext
from app.modules.games.engine.metadata import GameMetadata
from app.modules.games.engine.result import GameResult
from app.modules.games.engine.score import ScoreBreakdown


class BaseGame(ABC):
    metadata: GameMetadata

    async def can_start(self, context: GameContext) -> bool:
        return len(context.active_players) >= self.metadata.min_players

    @abstractmethod
    async def initialize(self, context: GameContext) -> None:
        """Membuat state awal game."""

    @abstractmethod
    async def start(self, context: GameContext) -> None:
        """Menjalankan game setelah lobby selesai."""

    @abstractmethod
    async def handle_message(self, context: GameContext, message: Any) -> None:
        """Menangani pesan yang relevan dengan game."""

    @abstractmethod
    async def handle_callback(self, context: GameContext, callback: Any) -> None:
        """Menangani tombol game."""

    @abstractmethod
    async def handle_timeout(self, context: GameContext, timer_key: str) -> None:
        """Menangani timeout ronde atau game."""

    @abstractmethod
    async def finish(self, context: GameContext, result: GameResult) -> None:
        """Menyelesaikan game."""

    async def restore(self, context: GameContext) -> None:
        """Memulihkan game setelah restart."""
        raise NotImplementedError

    async def calculate_scores(
        self, context: GameContext, result: GameResult
    ) -> dict[int, ScoreBreakdown]:
        """Hitung skor akhir tiap pemain (dipanggil `GameManager.finish_game()`
        sebelum commit ke `user_game_scores`). Default no-op (dict kosong) --
        game yang tidak punya sistem skor (mis. `simple_game`) tidak perlu
        override ini."""
        return {}
