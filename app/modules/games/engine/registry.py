from __future__ import annotations

from app.core.exceptions import GameNotFoundError
from app.modules.games.engine.base_game import BaseGame


class GameRegistry:
    def __init__(self) -> None:
        self._games: dict[str, BaseGame] = {}

    def register(self, game: BaseGame) -> None:
        game_key = game.metadata.key
        if game_key in self._games:
            raise ValueError(f"Game '{game_key}' sudah terdaftar")
        self._games[game_key] = game

    def get(self, game_key: str) -> BaseGame:
        try:
            return self._games[game_key]
        except KeyError as exc:
            raise GameNotFoundError(game_key) from exc

    def get_enabled(self) -> list[BaseGame]:
        return [game for game in self._games.values() if game.metadata.enabled]

    def find_by_deep_link_prefix(self, payload: str) -> BaseGame | None:
        """Cari game yang punya `deep_link_prefix` dan cocok dengan awal
        `payload` `/start` -- dipakai dispatcher deep link generik
        (`app/modules/games/deep_link.py`), bukan hanya untuk satu game."""
        for game in self._games.values():
            prefix = game.metadata.deep_link_prefix
            if prefix and payload.startswith(prefix):
                return game
        return None
