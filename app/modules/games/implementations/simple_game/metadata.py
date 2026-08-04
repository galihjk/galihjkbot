from __future__ import annotations

from app.modules.games.engine.metadata import GameMetadata

ROUND_TIMEOUT_SECONDS = 20

SIMPLE_GAME_METADATA = GameMetadata(
    key="simple_game",
    name="Test",
    description=(
        "Game percobaan untuk menguji fondasi engine (lobby, ready-check, "
        "kursi berebutan). Selesai dikembangkan (frozen) — dipertahankan "
        "apa adanya untuk uji pilihan game di /game, disembunyikan di production."
    ),
    min_players=3,
    max_players=8,
    lobby_timeout_seconds=60,
    ready_check_seconds=60,
)
