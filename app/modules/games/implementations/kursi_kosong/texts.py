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


def render_round_waiting(
    round_number: int,
    players: list[PlayerInfo],
    seat_total: int,
) -> str:
    """Teks ronde FASE 1: dikirim sebelum kursi/keyboard muncul. Belum ada
    ajakan memilih kursi (belum bisa diklik) dan belum menyebut hitungan
    waktu (timer belum mulai) — cukup "bersiap", sesuai nada MC."""
    return (
        f"🎵 RONDE {round_number} DIMULAI!\n"
        f"Tersisa {len(players)} pemain dan hanya tersedia {seat_total} kursi.\n\n"
        f"Bersiaplah! \n\nPilihan kursi akan segera muncul!"
    )


def render_round_ready(
    round_number: int,
    players: list[PlayerInfo],
    seat_total: int,
    timeout_seconds: int,
) -> str:
    """Teks ronde FASE 2: dikirim (via edit) BARENGAN kursi/keyboard
    dimunculkan — baru di titik ini ajakan memilih kursi & hitungan waktu
    masuk akal, karena timer memang baru mulai dihitung dari sini."""
    return (
        f"🎵 RONDE {round_number} DIMULAI!\n"
        f"Tersisa {len(players)} pemain dan hanya tersedia {seat_total} kursi.\n\n"
        f"Pilih kursinya SEKARANG! \n\nIngat, kursi boleh direbut. Harga diri ditanggung masing-masing."
        f"\n\nWaktu: {timeout_seconds} detik"
    )


def render_round_closed(
    round_number: int,
    seat_total: int,
    seats: dict[str, int],
    players_by_id: dict[int, str],
) -> str:
    """Snapshot penutup pesan ronde lama: daftar kursi final, TANPA narasi.

    Narasi hasil ronde (siapa tereliminasi dkk) dikirim terpisah lewat
    render_round_result — pesan ini cuma menutup pesan ronde sebelumnya
    supaya tidak kelihatan masih aktif (tombolnya juga dilepas).
    """
    lines = [f"🎵 RONDE {round_number} SELESAI"]
    for number in range(1, seat_total + 1):
        holder_id = seats.get(str(number))
        holder_name = players_by_id.get(holder_id, "?") if holder_id is not None else "(kosong)"
        lines.append(f"🪑 {number} · {holder_name}")
    return "\n".join(lines)


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
