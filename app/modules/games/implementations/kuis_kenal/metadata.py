from __future__ import annotations

from app.modules.games.engine.metadata import GameMetadata

GAME_KEY = "kuis_kenal"
GAME_NAME = "Kuis Kenal"
GAME_DESCRIPTION = (
    "Jawab pertanyaan tentang temanmu dan buktikan siapa yang paling mengenal mereka."
)

DEEP_LINK_PREFIX = "kk-"

QUESTION_OPTIONS_PER_TURN = 5
QUESTION_REROLL_LIMIT = 1
ANSWER_MAX_LENGTH = 300

QUESTION_PICK_TIMEOUT_SECONDS = 60
ANSWER_TIMEOUT_SECONDS = 120
JUDGING_TIMEOUT_SECONDS = 120

MESSAGE_PAUSE_SECONDS = 2
REVEAL_MIN_SECONDS = 2
REVEAL_MAX_SECONDS = 4
EDIT_RETRY_DELAYS = (0, 0.5, 1.5)

# Berapa lama konteks input privat (§Tahap 0) tetap aktif setelah user
# membuka deep link -- longgar (2x timeout fase) supaya tidak kedaluwarsa
# duluan hanya karena user lama mengetik, tapi tetap terbatas (bukan tanpa
# batas) supaya tidak nyangkut selamanya kalau ronde sudah lanjut duluan.
QUESTION_PICK_CONTEXT_TTL_SECONDS = QUESTION_PICK_TIMEOUT_SECONDS * 2
ANSWER_CONTEXT_TTL_SECONDS = ANSWER_TIMEOUT_SECONDS * 2
JUDGE_CONTEXT_TTL_SECONDS = JUDGING_TIMEOUT_SECONDS * 2

HOW_TO_PLAY = (
    "🧠 CARA MAIN — Kuis Kenal\n\n"
    "Tiap giliran, satu pemain jadi \"subjek\" dan memilih 1 dari 5 pertanyaan "
    "lewat chat privat bot. Pertanyaan itu diumumkan ke grup, lalu pemain "
    "LAIN menjawab lewat chat privat (bebas tebak, bukan pilihan ganda).\n\n"
    "• Semua jawaban dikonfirmasi dulu sebelum final -- tidak bisa asal ketik.\n"
    "• Subjek memeriksa semua jawaban secara ANONIM dan menandai mana yang "
    "dianggap benar (boleh lebih dari satu).\n"
    "• Tiap jawaban yang ditandai benar dapat 1 poin.\n"
    "• Semua pemain gantian jadi subjek tepat sekali.\n\n"
    "Minimal 3, maksimal 10 pemain per game."
)

KUIS_KENAL_METADATA = GameMetadata(
    key=GAME_KEY,
    name=GAME_NAME,
    description=GAME_DESCRIPTION,
    min_players=3,
    max_players=10,
    lobby_timeout_seconds=60,
    ready_check_seconds=60,
    deep_link_prefix=DEEP_LINK_PREFIX,
    how_to_play=HOW_TO_PLAY,
)
