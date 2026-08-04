from __future__ import annotations

from app.modules.games.engine.context import PlayerInfo

WELCOME_TEXT = (
    "🎙️ Selamat datang di KURSI KOSONG! Permainan yang menguji kecepatan, "
    "keberuntungan, dan kemampuan manusia memperebutkan furnitur. Setiap "
    "ronde memiliki satu kursi lebih sedikit daripada jumlah pemain. Pemain "
    "yang tidak mendapatkan kursi akan tereliminasi. Bersiaplah. Musik akan "
    "segera dimulai!"
)

SEAT_ALREADY_MINE_ALERT = "Kamu sudah duduk di Kursi {seat}. Jangan pindah-pindah, kursinya bukan kontrakan."
SEAT_TAKEN_ALERT = "Kursi ini sudah ditempati {holder}. Pilih kursi lain!"
NOT_IN_GAME_ALERT = "Kamu tidak dalam permainan ini."
STALE_ROUND_ALERT = "Tampilan ini sudah kedaluwarsa. Gunakan tombol pada pesan terbaru."
SEAT_CLAIMED_TOAST = "✅ Kursi {seat} berhasil diamankan!"


def render_round_start(
    round_number: int,
    players: list[PlayerInfo],
    seat_total: int,
    timeout_seconds: int,
) -> str:
    return (
        f"🎵 RONDE {round_number} DIMULAI!\n"
        f"Tersisa {len(players)} pemain dan hanya tersedia {seat_total} kursi.\n"
        f"Musik mulai dimainkan. Silakan memilih kursi sebelum {timeout_seconds} "
        f"detik berakhir.\n"
        f"Ingat, kursi boleh direbut. Harga diri ditanggung masing-masing."
    )


def render_round_result(eliminated_name: str | None, survivor_names: list[str]) -> str:
    lines = []
    if eliminated_name:
        lines.append(
            f"☠️ {eliminated_name} tidak mendapatkan kursi. Terima kasih sudah "
            "berdiri bersama kami."
        )
    else:
        lines.append("Ronde selesai.")
    lines.append("")
    lines.append("Pemain tersisa:")
    lines.extend(f"- {name}" for name in survivor_names)
    return "\n".join(lines)


def render_winner(winner_name: str) -> str:
    return (
        f"🏆 KITA PUNYA PEMENANG! {winner_name} berhasil menguasai kursi "
        "terakhir dan resmi menjadi Raja Furnitur hari ini!"
    )
