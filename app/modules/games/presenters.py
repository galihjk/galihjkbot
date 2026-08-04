from __future__ import annotations

from app.core.enums import GameStatus
from app.database.models.game_session import GameSession
from app.modules.games.engine.metadata import GameMetadata

_STATUS_LABELS = {
    GameStatus.LOBBY.value: "Menunggu pemain",
    GameStatus.STARTING.value: "Segera dimulai",
    GameStatus.RUNNING.value: "Berlangsung",
}


def format_game_status(
    game_session: GameSession, metadata: GameMetadata, player_count: int
) -> str:
    label = _STATUS_LABELS.get(game_session.status, game_session.status)
    return (
        f"🎮 {metadata.name}\n"
        f"Status : {label}\n"
        f"Pemain : {player_count}/{metadata.max_players}"
    )
