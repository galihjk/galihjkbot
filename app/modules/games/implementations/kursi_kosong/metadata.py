from __future__ import annotations

from app.modules.games.engine.metadata import GameMetadata

ROUND_TIMEOUT_SECONDS = 15
MESSAGE_PAUSE_SECONDS = 2       # jeda umum antar-pesan berurutan dalam game
SEAT_REVEAL_MIN_SECONDS = 3     # jeda acak sebelum keyboard kursi dimunculkan (batas bawah)
SEAT_REVEAL_MAX_SECONDS = 5     # jeda acak sebelum keyboard kursi dimunculkan (batas atas)
CONTEST_WINDOW_SECONDS = 1.2    # jendela rebutan kursi (§12 desain)
MIN_ACTION_WINDOW_SECONDS = 6   # floor keadilan: ronde selesai lebih cepat dari ini -> pemain yang belum beraksi TIDAK dicap AFK (lihat development-history.md)

KURSI_KOSONG_METADATA = GameMetadata(
    key="kursi_kosong",
    name="🪑Kursi🪑Kosong🪑",
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
