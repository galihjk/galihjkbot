from __future__ import annotations

from app.modules.games.engine.metadata import GameMetadata

ROUND_TIMEOUT_SECONDS = 15

KURSI_KOSONG_METADATA = GameMetadata(
    key="kursi_kosong",
    name="Kursi Kosong",
    description=(
        "Permainan kursi musik ala Telegram. Tiap ronde kursi selalu satu "
        "lebih sedikit dari jumlah pemain — yang tidak kebagian kursi "
        "tereliminasi. Bertahan sampai jadi yang terakhir duduk!"
    ),
    min_players=3,
    max_players=8,
    lobby_timeout_seconds=60,
    ready_check_seconds=60,
)
