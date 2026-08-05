from __future__ import annotations

import random

from app.modules.games.engine.context import PlayerInfo
from app.modules.games.implementations.kursi_kosong.scoring import PlayerScoreResult

WELCOME_TEXT = (
    "🎙️ Selamat datang di KURSI KOSONG! Permainan yang menguji kecepatan, "
    "keberuntungan, dan kemampuan manusia memperebutkan furnitur. Setiap "
    "ronde memiliki satu kursi lebih sedikit daripada jumlah pemain. Pemain "
    "yang tidak mendapatkan kursi akan tereliminasi. Bersiaplah. Musik akan "
    "segera dimulai!"
)

SEAT_ALREADY_MINE_ALERT = "Kamu sudah duduk di Kursi {seat}. Jangan pindah-pindah, kursinya bukan kontrakan."
NOT_IN_GAME_ALERT = "Kamu tidak dalam permainan ini."
STALE_ROUND_ALERT = "Tampilan ini sudah kedaluwarsa. Gunakan tombol pada pesan terbaru."
CONTESTING_TOAST = "⚔️ Kamu sedang memperebutkan Kursi {seat}."
ALREADY_CONTESTING_ALERT = "Kamu masih menunggu hasil rebutan Kursi {seat} sebelumnya. Selesaikan itu dulu."

# §43 desain: "Klik kursi terisi" -- tetap toast pribadi (bukan pesan grup
# baru, lihat catatan di kursi-kosong-implementation-plan.md Tahap 3),
# isinya diperkaya lewat bank + random.choice.
SEAT_TAKEN_ALERTS = [
    "🤨 Kamu mencoba duduk di pangkuan {holder}. Panitia tidak menyediakan fitur tersebut.",
    "🛋️ Kursi ini sudah ditempati {holder}. Jangan coba mengubahnya jadi sofa keluarga.",
]

# §43 desain: "Kalah perebutan" -- outro narasi rebutan kursi.
CONTEST_LOSER_TAUNTS = [
    "kembali berdiri sambil berpura-pura tidak kecewa.",
    "kembali berdiri, gravitasi bekerja lebih cepat dari harapan mereka.",
]

# §43 desain: "AFK" -- dipakai di render_round_result kalau yang tereliminasi
# tidak melakukan aksi valid apa pun sepanjang ronde.
AFK_ELIMINATION_BANK = [
    "💤 {name} tampaknya sedang berdiskusi dengan alam bawah sadar, bukan memilih kursi.",
    "🛰️ Sinyal dari {name} belum berhasil diterima pusat kendali. Dianggap tidak hadir.",
]

# §43 desain: "Eliminasi" -- dipakai di render_round_result untuk eliminasi
# wajar (sudah beraksi, cuma kalah/kehabisan kursi).
NORMAL_ELIMINATION_BANK = [
    "☠️ {name} tidak mendapatkan kursi. Terima kasih sudah berdiri bersama kami.",
    "🕊️ {name} gugur dengan terhormat, meskipun sebenarnya cuma tidak kebagian tempat.",
]

COUNTDOWN_NOTES = {
    5: "⏳ Lima detik lagi! Yang masih berdiri, silakan panik secara profesional.",
    3: "🚨 Tiga detik! Kursi tidak menunggu siapa pun.",
}

FINAL_ROUND_HEADER = (
    "🔥 RONDE FINAL! Dua pemain. Satu kursi. Tidak ada teman, tidak ada belas "
    "kasihan, hanya ada callback query."
)


def _round_header(round_number: int, players: list[PlayerInfo], seat_total: int, is_final: bool) -> str:
    """Header pembuka teks ronde -- diganti flourish ronde final (§25
    desain) kalau tinggal 2 pemain/1 kursi, dipakai FASE 1 & FASE 2 supaya
    tidak duplikasi cabang kondisi."""
    if is_final:
        return FINAL_ROUND_HEADER
    return (
        f"🎵 RONDE {round_number} DIMULAI!\n"
        f"Tersisa {len(players)} pemain dan hanya tersedia {seat_total} kursi."
    )


def render_round_waiting(
    round_number: int,
    players: list[PlayerInfo],
    seat_total: int,
    is_final: bool = False,
) -> str:
    """Teks ronde FASE 1: dikirim sebelum kursi/keyboard muncul. Belum ada
    ajakan memilih kursi (belum bisa diklik) dan belum menyebut hitungan
    waktu (timer belum mulai) — cukup "bersiap", sesuai nada MC."""
    header = _round_header(round_number, players, seat_total, is_final)
    return f"{header}\n\nBersiaplah! \n\nPilihan kursi akan segera muncul!"


def render_round_ready(
    round_number: int,
    players: list[PlayerInfo],
    seat_total: int,
    timeout_seconds: int,
    is_final: bool = False,
    extra_note: str | None = None,
) -> str:
    """Teks ronde FASE 2: dikirim (via edit) BARENGAN kursi/keyboard
    dimunculkan — baru di titik ini ajakan memilih kursi & hitungan waktu
    masuk akal, karena timer memang baru mulai dihitung dari sini.

    `extra_note` (opsional): baris tambahan di akhir, dipakai reminder
    countdown 5/3 detik (§24 desain) saat pesan ini di-edit ulang.
    """
    header = _round_header(round_number, players, seat_total, is_final)
    text = (
        f"{header}\n\n"
        f"Pilih kursinya SEKARANG! \n\nIngat, kursi boleh direbut. Harga diri ditanggung masing-masing."
        f"\n\nWaktu: {timeout_seconds} detik"
    )
    if extra_note:
        text += f"\n\n{extra_note}"
    return text


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


def render_contest_result(
    seat_number: int,
    contestant_names: list[str],
    winner_name: str,
    loser_names: list[str],
) -> str:
    """Narasi rebutan kursi (dikirim SATU KALI saat kontes selesai, bukan
    tiap klik individual, sesuai §23 desain). Kalimat pembuka beda untuk 2
    orang vs lebih dari 2 (§14 desain)."""
    if len(contestant_names) == 2:
        intro = (
            f"💥 {contestant_names[0]} dan {contestant_names[1]} tiba di Kursi "
            f"{seat_number} hampir bersamaan. Satu kursi, dua ambisi, nol musyawarah."
        )
    else:
        intro = (
            f"🚨 {len(contestant_names)} pemain menyerbu Kursi {seat_number}. "
            f"Kursinya satu, rasa percaya diri mereka ber-{len(contestant_names)}."
        )
    losers_text = ", ".join(loser_names)
    taunt = random.choice(CONTEST_LOSER_TAUNTS)
    outro = f"🏆 {winner_name} berhasil mengamankan Kursi {seat_number}! {losers_text} {taunt}"
    return f"{intro}\n{outro}"


def render_round_result(
    normal_names: list[str], afk_names: list[str], survivor_names: list[str]
) -> str:
    """Narasi hasil ronde. `normal_names`/`afk_names` bisa berisi lebih dari
    satu nama -- eliminasi bisa lebih dari 1 orang sekaligus sejak revisi
    aturan pasca-Tahap 3 (kursi yang tidak pernah diklaim tetap kosong,
    bukan diisi acak lagi; lihat development-history.md). Nama digabung
    koma kalau lebih dari satu, dipakai apa adanya di template bank yang
    sudah ada (dirancang untuk 1 nama, tetap terbaca wajar untuk beberapa)."""
    lines = []
    if normal_names:
        lines.append(
            random.choice(NORMAL_ELIMINATION_BANK).format(name=", ".join(normal_names))
        )
    if afk_names:
        lines.append(
            random.choice(AFK_ELIMINATION_BANK).format(name=", ".join(afk_names))
        )
    if not normal_names and not afk_names:
        lines.append("Ronde selesai.")
    lines.append("")
    lines.append("Pemain tersisa:")
    if survivor_names:
        lines.extend(f"- {name}" for name in survivor_names)
    else:
        lines.append("- (tidak ada)")
    return "\n".join(lines)


def render_no_winner() -> str:
    """Kasus ekstrem: tidak ada satu kursi pun diklaim di ronde itu -- semua
    pemain hidup tereliminasi bersamaan. MC mengumumkan tidak ada pemenang
    (bukan pesan error/gagal seperti jalur §39 desain -- ini hasil wajar
    permainan, bukan kegagalan sistem)."""
    return (
        "🎙️ Musik berhenti... tapi tidak ada satu pun yang berebut kursi. "
        "Sepertinya semua orang lupa cara duduk. Permainan resmi berakhir "
        "tanpa pemenang kali ini!"
    )


def render_winner(winner_name: str) -> str:
    return (
        f"🏆 KITA PUNYA PEMENANG! {winner_name} berhasil menguasai kursi "
        "terakhir dan resmi menjadi Raja Furnitur hari ini!"
    )


_MEDALS = ["🥇", "🥈", "🥉"]


def render_final_results(
    results: dict[int, PlayerScoreResult], names_by_id: dict[int, str]
) -> str:
    """Format hasil akhir + skor (§45 desain) -- diurutkan skor akhir
    descending, medali untuk 3 teratas, baris AFK wajib menyebut angka
    penalti eksplisit (§19), bukan cuma label "AFK"."""
    ordered = sorted(
        results.items(), key=lambda kv: kv[1].breakdown.final_score, reverse=True
    )
    lines = ["🏆 HASIL AKHIR KURSI KOSONG"]
    for index, (user_id, res) in enumerate(ordered):
        name = names_by_id.get(user_id, "?")
        final = res.breakdown.final_score
        if res.penalty is not None:
            lines.append(f"💤 {name} (Penalti AFK {res.penalty} poin) - {final} poin")
        else:
            prefix = _MEDALS[index] if index < len(_MEDALS) else f"{index + 1}."
            lines.append(f"{prefix} {name} — {final} poin")
    lines.append("")
    lines.append(
        "Terima kasih sudah bermain. Kursi boleh habis, persahabatan semoga tidak."
    )
    return "\n".join(lines)
