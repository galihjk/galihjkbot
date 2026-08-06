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
    how_to_play=(
        "🪑 CARA MAIN — Kursi Kosong\n\n"
        "Tiap ronde, jumlah kursi selalu 1 lebih sedikit dari jumlah pemain aktif. "
        "Klik tombol kursi buat menempatinya sebelum waktu ronde (15 detik) habis.\n\n"
        "• Kalau 2 pemain klik kursi yang sama duluan → terjadi rebutan, cuma 1 yang menang.\n"
        "• Pemain yang sudah duduk tidak bisa pindah kursi lagi.\n"
        "• Yang tidak kebagian kursi saat ronde habis → tereliminasi.\n"
        "• Bertahan terus sampai jadi 1 pemain terakhir = MENANG.\n\n"
        "Minimal 3, maksimal 8 pemain per game."
    ),
)
