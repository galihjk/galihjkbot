from __future__ import annotations

from html import escape

from app.modules.games.engine.context import PlayerInfo

WELCOME_TEXT = (
    "🧠 KUIS KENAL dimulai!\n\n"
    "Tiap giliran, satu pemain jadi \"subjek\" dan memilih 1 dari 5 pertanyaan "
    "lewat chat privat bot. Pemain lain menjawab lewat chat privat juga, lalu "
    "subjek yang menilai jawaban mana yang paling tepat.\n\n"
    "Semua pemain akan gantian jadi subjek tepat sekali. Siap-siap!"
)

NOT_IN_GAME_ALERT = "Kamu tidak dalam permainan ini."
STALE_INTERACTION_ALERT = "Tampilan ini sudah kedaluwarsa, tunggu pembaruan terbaru."
NOT_YOUR_TURN_TO_PICK_ALERT = "Bukan giliranmu memilih soal."
SUBJECT_CANNOT_ANSWER_OWN_TURN_ALERT = "Kamu tidak bisa menjawab pertanyaan tentang dirimu sendiri."
ALREADY_CONFIRMED_ALERT = "Jawabanmu sudah final, tidak bisa diubah lagi."
NO_DRAFT_TO_CONFIRM_ALERT = "Belum ada jawaban yang bisa dikonfirmasi, ketik dulu jawabanmu."
REROLL_LIMIT_REACHED_ALERT = "Kamu sudah pakai kesempatan ambil ulang soal."
ONLY_SUBJECT_CAN_JUDGE_ALERT = "Hanya subjek giliran ini yang bisa menilai jawaban."
INVALID_LINK_ALERT = "Link ini sudah tidak berlaku."
NOT_A_PARTICIPANT_ALERT = "Kamu bukan peserta game ini."
ANSWER_EMPTY_ALERT = "Jawaban tidak boleh kosong."
ANSWER_TOO_LONG_ALERT = "Jawaban terlalu panjang, coba diringkas ya."
ANSWER_MUST_BE_TEXT_ALERT = "Jawaban harus berupa teks ya, bukan foto/stiker/dll."
ANSWER_CANNOT_BE_COMMAND_ALERT = "Itu kelihatan seperti command, bukan jawaban. Coba ketik ulang."


def mention(player: PlayerInfo) -> str:
    name = escape(player.display_name)
    return f'<a href="tg://user?id={player.telegram_user_id}">{name}</a>'


def format_question_text(question_text: str, subject_label: str) -> str:
    return question_text.format(subject=subject_label)


def render_turn_start(subject: PlayerInfo, round_number: int, total_turns: int) -> str:
    return (
        f"🔔 Giliran {round_number}/{total_turns}\n\n"
        f"Sekarang giliran {mention(subject)} jadi subjek pertanyaan!\n"
        f"Menunggu {mention(subject)} pilih soal lewat chat privat bot..."
    )


def render_question_options(question_texts: list[str]) -> str:
    numbers = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣")
    lines = ["📝 Pilih salah satu pertanyaan ini (soal akan diumumkan ke grup):", ""]
    for i, text in enumerate(question_texts):
        label = numbers[i] if i < len(numbers) else f"{i + 1}."
        lines.append(f"{label} {escape(text)}")
    return "\n".join(lines)


def render_question_selected_ack() -> str:
    return "✅ Soal terpilih, sudah diumumkan ke grup. Tunggu jawaban dari pemain lain ya."


def render_public_question(question_text: str, subject: PlayerInfo) -> str:
    return (
        f"🎯 Pertanyaan untuk {mention(subject)}:\n\n"
        f"<b>{escape(question_text)}</b>\n\n"
        "Pemain lain, buka chat privat bot untuk menjawab (tombol di bawah)!"
    )


def render_private_answer_prompt(question_text: str, subject: PlayerInfo) -> str:
    return (
        f"🎯 Pertanyaan tentang {mention(subject)}:\n\n"
        f"<b>{escape(question_text)}</b>\n\n"
        "Ketik jawabanmu (bebas, bukan pilihan ganda). Jawaban ini bakal diperiksa "
        f"{mention(subject)} secara anonim -- jadi nama kamu tidak akan terlihat "
        "saat dinilai."
    )


def render_answer_confirmation(answer_text: str) -> str:
    return f"Jawabanmu:\n\n“{escape(answer_text)}”\n\nSudah yakin?"


def render_answer_recorded() -> str:
    return "✅ Jawaban kamu sudah tercatat. Tunggu pemain lain & hasil dari subjek ya."


def render_answer_change_prompt() -> str:
    return "Oke, ketik jawaban barumu."


def render_waiting_for_players(confirmed: int, total: int) -> str:
    return f"⏳ Menunggu jawaban... ({confirmed}/{total} pemain sudah konfirmasi)"


def render_judging_started_public(subject: PlayerInfo) -> str:
    return f"✅ Semua jawaban sudah masuk. {mention(subject)} sedang menilai jawaban..."


def render_judging_intro(question_text: str) -> str:
    return (
        f"🔍 Semua jawaban sudah masuk untuk:\n\n<b>{escape(question_text)}</b>\n\n"
        "Ini jawaban dari pemain lain (ANONIM, sudah dikelompokkan yang mirip). "
        "Tandai kelompok mana yang kamu anggap BENAR (boleh lebih dari satu), "
        "lalu tekan tombol selesai."
    )


def render_judging(groups: list[dict]) -> str:
    lines = ["Daftar jawaban:"]
    for i, group in enumerate(groups, start=1):
        lines.append(f"{i}. {escape(group['display_text'])}")
    return "\n".join(lines)


def render_turn_result(
    question_text: str,
    successful: list[tuple[PlayerInfo, str]],
    failed: list[tuple[PlayerInfo, str | None]],
) -> str:
    lines = [f"<b>{escape(question_text)}</b>", "", "Pemain yang berhasil menebak:"]
    if successful:
        for player, answer_text in successful:
            lines.append(f"• {mention(player)}: {escape(answer_text)}")
    else:
        lines.append("TIDAK ADA")
        lines.append("")
        lines.append("Silakan tanya sendiri jawaban yang benernya apa...")

    lines.append("")
    lines.append("Pemain yang tidak berhasil:")
    if failed:
        for player, answer_text in failed:
            text = escape(answer_text) if answer_text else "Tidak menjawab"
            lines.append(f"• {mention(player)}: {text}")
    else:
        lines.append("TIDAK ADA")

    return "\n".join(lines)


def render_scoreboard(rankings: list[tuple[PlayerInfo, int]]) -> str:
    lines = ["📊 Skor sementara"]
    for i, (player, score) in enumerate(rankings, start=1):
        lines.append(f"{i}. {mention(player)} — {score}")
    return "\n".join(lines)


def render_final_result(
    rankings: list[tuple[PlayerInfo, int]], winner_ids: list[int]
) -> str:
    lines = ["🏁 KUIS KENAL SELESAI!", ""]
    if len(winner_ids) == 1:
        winner = next(p for p, _ in rankings if p.user_id == winner_ids[0])
        lines.append(f"🏆 {mention(winner)} menang!")
    elif winner_ids:
        names = [mention(p) for p, _ in rankings if p.user_id in winner_ids]
        lines.append("🏆 Seri! Pemenang: " + ", ".join(names))
    lines.append("")
    lines.append(render_scoreboard(rankings))
    return "\n".join(lines)


def render_subject_pick_timeout(subject: PlayerInfo) -> str:
    return (
        f"⏰ {mention(subject)} tidak memilih soal tepat waktu. "
        "Giliran ini dilewati, lanjut ke pemain berikutnya."
    )


def render_judge_timeout(subject: PlayerInfo) -> str:
    return (
        f"⏰ {mention(subject)} tidak menyelesaikan penilaian tepat waktu. "
        "Giliran ini dibatalkan tanpa poin, lanjut ke pemain berikutnya."
    )


def render_timeout(kind: str, subject: PlayerInfo) -> str:
    if kind == "question_pick":
        return render_subject_pick_timeout(subject)
    if kind == "judge":
        return render_judge_timeout(subject)
    raise ValueError(f"Jenis timeout tidak dikenal: {kind}")


def render_stale_interaction() -> str:
    return STALE_INTERACTION_ALERT


def render_no_active_private_prompt_hint() -> str:
    return (
        "Sesi privatmu sudah tidak aktif (mungkin sudah kedaluwarsa atau "
        "giliran sudah lanjut). Buka lagi tombol di pesan grup terbaru ya."
    )
