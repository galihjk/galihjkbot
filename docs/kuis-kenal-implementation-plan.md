# Kuis Kenal — Implementation Plan

## 1. Tujuan

Membangun game Telegram **Kuis Kenal** dengan alur utama:

```text
Buat antrean giliran
        │
        ▼
Pemain aktif memilih soal
        │
        ▼
Pemain lain menjawab lewat chat privat
        │
        ▼
Setiap pemain mengonfirmasi jawabannya
        │
        ▼
Pemain aktif memeriksa jawaban
        │
        ▼
Skor ronde diperbarui
        │
        ├─ Masih ada giliran → mulai giliran berikutnya
        └─ Giliran habis → tampilkan skor akhir dan selesaikan game
```

Implementasi wajib:

- Menggunakan lifecycle generik `LOBBY → STARTING → RUNNING → FINISHED/CANCELLED`.
- Memakai lobby, ready-check, timer, lock, penyimpanan, recovery, dan leaderboard milik engine.
- Menyimpan state permainan dalam `GameSession.state_json`.
- Mendukung jawaban teks bebas melalui chat privat bot.
- Menggunakan `context.acting_user_id` sebagai identitas pemain.
- Aman terhadap callback lama, klik ganda, timeout bersamaan, pesan Telegram gagal diedit, dan tautan privat kedaluwarsa.
- Tidak mencoba melanjutkan sesi `RUNNING` sesudah restart; sesi diperlakukan sesuai kebijakan recovery engine.

## 2. Identitas game

```python
GAME_KEY = "kuis_kenal"
GAME_NAME = "Kuis Kenal"
GAME_DESCRIPTION = "Jawab pertanyaan tentang temanmu dan buktikan siapa yang paling mengenal mereka."
```

Metadata awal:

```python
GameMetadata(
    key="kuis_kenal",
    name="Kuis Kenal",
    description="Jawab pertanyaan tentang temanmu dan buktikan siapa yang paling mengenal mereka.",
    min_players=3,
    max_players=10,
    lobby_timeout_seconds=60,
    ready_check_seconds=60,
)
```

Minimum tiga pemain diperlukan karena satu pemain menjadi pemain aktif dan minimal dua pemain lain menjawab.

## 3. Keputusan arsitektur untuk jawaban privat

### 3.1 Kesenjangan yang perlu ditutup

Kontrak `BaseGame.handle_message()` tersedia, tetapi panduan saat ini hanya menjamin pengiriman pesan teks grup selama status `RUNNING`. Jawaban teks bebas dari chat privat tidak dapat dihubungkan ke sesi game hanya dari isi pesan biasa.

Karena itu, sebelum membuat alur jawaban privat, tambahkan **jembatan input privat generik**. Jembatan ini bukan logika Kuis Kenal dan harus bisa dipakai game lain.

### 3.2 Komponen generik baru

Struktur yang disarankan:

```text
app/modules/games/
├── private_input.py
└── handlers/
    └── private_game_messages.py
```

Tanggung jawabnya:

1. Mendaftarkan konteks input privat aktif untuk seorang user.
2. Menghubungkan pesan privat berikutnya ke `session_id` yang benar.
3. Meneruskan pesan ke jalur `GameManager` yang akhirnya memanggil `BaseGame.handle_message()`.
4. Tidak membaca atau mengubah state spesifik Kuis Kenal.
5. Menghapus konteks setelah jawaban final, kedaluwarsa, game selesai, game dibatalkan, atau proses restart.

Bentuk data minimum:

```python
@dataclass
class PendingPrivateInput:
    user_id: int
    session_id: int
    purpose: str
    round_number: int
    nonce: str
    expires_at: datetime
```

API minimum:

```python
register_private_input(...)
get_private_input(user_id)
clear_private_input(user_id)
clear_session_private_inputs(session_id)
```

Penyimpanan awal boleh in-memory karena kebijakan engine memang membatalkan sesi `RUNNING` saat restart. Tidak perlu memulihkan konteks input privat setelah proses hidup kembali.

### 3.3 Aktivasi melalui deep link

Tombol grup membuka bot dengan payload ringkas:

```text
https://t.me/<bot_username>?start=kk-a-<session>-<round>-<nonce>
```

Jenis payload:

```text
kk-q  → pemain aktif membuka pemilihan soal
kk-a  → pemain lain membuka mode jawab
kk-j  → pemain aktif membuka pemeriksaan jawaban
```

Ketentuan:

- Payload harus muat dalam batas Telegram `/start`.
- `session_id` dan nomor ronde dapat diubah ke base36 agar ringkas.
- `nonce` acak disimpan di `state_json` dan diverifikasi sebelum konteks privat diaktifkan.
- Link ronde lama ditolak.
- User yang bukan peserta ditolak.
- Pemain aktif tidak boleh membuka mode jawab pada rondenya sendiri.
- Membuka konteks baru menggantikan konteks privat lama milik user dan bot menjelaskan sesi mana yang sedang aktif.

## 4. Alur hidup game

```text
/game kuis_kenal
      │
      ▼
LOBBY generik
      │
      ▼
READY-CHECK generik
      │
      ▼
RUNNING
      │
      ├─ initialize(): buat antrean acak dan state awal
      └─ start(): kirim pembukaan dan mulai giliran pertama
```

Game tidak mengubah status lifecycle secara langsung. Penyelesaian normal dilakukan melalui:

```python
await context.game_manager.finish_game(context, result)
```

## 5. Alur satu giliran

### 5.1 Mulai giliran

1. Ambil pemain pertama dari antrean giliran.
2. Tetapkan sebagai `current_subject_id`.
3. Ambil lima pertanyaan yang belum digunakan.
4. Kirim pesan grup bahwa pemain aktif harus memilih soal.
5. Tampilkan tombol deep link `📝 Pilih Soal`.
6. Jadwalkan timeout pemilihan soal.

### 5.2 Pemain aktif memilih soal

1. Pemain aktif membuka bot privat dari deep link.
2. Bot menampilkan lima pertanyaan bernomor.
3. Inline keyboard cukup memakai label `1️⃣` sampai `5️⃣`; teks lengkap tetap berada di badan pesan.
4. Pemain memilih satu pertanyaan.
5. Pilihan disimpan dan seluruh pertanyaan yang ditawarkan dimasukkan ke daftar sudah digunakan agar paket yang sama tidak muncul lagi.
6. Bot menutup keyboard pemilihan soal.
7. Pertanyaan terpilih dipublikasikan ke grup.
8. Pemain lain mendapat tombol `✍️ Jawab Privat`.

Opsional MVP:

- Tombol `🔀 Ambil 5 soal lain` maksimal satu kali per giliran.
- Lima soal lama tetap dianggap sudah digunakan.

### 5.3 Pemain lain menjawab privat

1. Pemain membuka tombol `✍️ Jawab Privat`.
2. Bot mengaktifkan konteks privat untuk sesi dan ronde tersebut.
3. Bot menampilkan pertanyaan dan pemberitahuan bahwa jawaban final akan diperiksa pemain aktif.
4. Pemain mengirim jawaban teks bebas.
5. Jawaban disimpan sebagai draft, belum final.
6. Bot menampilkan kembali jawaban dan tombol konfirmasi.

Contoh:

```text
Jawabanmu:

"Kabur ke warung lalu pura-pura lupa jalan pulang."

Sudah yakin?

[✅ Ya, kirim] [✏️ Ubah]
```

### 5.4 Konfirmasi jawaban

Jika memilih `✅ Ya, kirim`:

- Draft dipindahkan menjadi jawaban final.
- Waktu konfirmasi dicatat.
- Konteks input privat dibersihkan.
- Pesan konfirmasi ditutup dan keyboard dilepas.
- Pemain tidak dapat mengubah jawaban final.

Jika memilih `✏️ Ubah`:

- Draft sebelumnya dibuang atau dipertahankan hanya untuk tampilan.
- Revisi jawaban dinaikkan.
- Konteks input privat diaktifkan kembali.
- Callback konfirmasi lama menjadi kedaluwarsa.

Jika semua pemain selain pemain aktif sudah mengonfirmasi sebelum timer habis, fase menjawab langsung selesai.

### 5.5 Pemain aktif memeriksa jawaban

Setelah semua jawaban final masuk atau timer menjawab habis:

1. Batalkan timer menjawab.
2. Tutup tombol jawab pada pesan grup.
3. Kirim pesan privat kepada pemain aktif bahwa jawaban siap diperiksa.
4. Tampilkan jawaban secara anonim agar penilaian tidak dipengaruhi nama pemain.
5. Jawaban yang sama setelah normalisasi ringan digabung menjadi satu kelompok.
6. Pemain aktif dapat menandai satu atau beberapa kelompok sebagai benar.
7. Caption tombol penyelesaian mengikuti state penilaian:
   - Belum ada satu pun kelompok ditandai benar: `TIDAK ADA YANG BENAR`.
   - Minimal satu kelompok ditandai benar: `✅ Selesai Menilai`.
8. Menekan salah satu caption tersebut langsung menyelesaikan penilaian tanpa dialog konfirmasi tambahan.
9. Perubahan toggle wajib memperbarui caption tombol pada pesan penilaian yang sama.
10. Callback penyelesaian tetap idempoten: klik ganda atau callback terlambat tidak boleh memproses skor dua kali.

Normalisasi hanya untuk pengelompokan, bukan penentuan otomatis:

```text
- Unicode NFKC
- trim awal/akhir
- ubah ke lowercase
- gabungkan whitespace berulang
- pertahankan teks asli untuk tampilan
```

Sistem tidak menentukan benar/salah berdasarkan kemiripan string. Keputusan tetap milik pemain aktif.

### 5.6 Hasil giliran

Setelah penilaian selesai:

1. Tambahkan satu poin internal kepada setiap pemain yang jawabannya ditandai benar.
2. Catat statistik aktivitas dan jawaban benar.
3. Tutup pesan privat penilaian dan lepaskan keyboard-nya.
4. Kirim pesan hasil giliran ke grup yang berisi pertanyaan, pemain yang berhasil, pemain yang tidak berhasil, dan jawaban masing-masing.
5. Nama pemain pada kedua daftar wajib berupa mention HTML `tg://user?id=` dan sudah melalui `html.escape()`.
6. Teks jawaban juga wajib di-escape sebelum dimasukkan ke pesan HTML.
7. Pemain yang tidak mengirim jawaban final tetap masuk daftar pemain yang tidak berhasil dengan isi `Tidak menjawab`.
8. Kirim klasemen sementara sebagai pesan TERPISAH setelah pesan hasil giliran.
9. Setelah jeda pacing, lanjutkan antrean atau selesaikan game.

Contoh hasil jika ada jawaban benar:

```text
Apa yang dilakukan Naya jika dipanggil guru saat di luar sekolah?

Pemain yang berhasil menebak:
• Galih: Kabur ke warung
• Rani: Pura-pura tidak dengar

Pemain yang tidak berhasil:
• Raka: tidur
• Alya: lapor polisi
```

Pada implementasi nyata, `Galih`, `Rani`, `Raka`, dan `Alya` dirender sebagai mention, bukan teks nama biasa.

Contoh jika tidak ada jawaban yang ditandai benar:

```text
Apa yang dilakukan Naya jika dipanggil guru saat di luar sekolah?

Pemain yang berhasil menebak:
TIDAK ADA

Silakan tanya sendiri jawaban yang benernya apa...

Pemain yang tidak berhasil:
• Galih: Kabur ke warung
• Rani: Pura-pura tidak dengar
• Raka: tidur
• Alya: lapor polisi
```

Pesan berikutnya baru menampilkan skor:

```text
📊 Skor sementara
1. Galih — 3
2. Rani — 2
3. Raka — 1
4. Alya — 0
```

### 5.7 Giliran berikutnya atau selesai

```text
turn_queue masih berisi pemain
    → reset state ronde
    → ambil pemain berikutnya
    → mulai pemilihan soal baru

turn_queue kosong
    → bangun GameResult
    → tampilkan skor akhir
    → finish_game()
```

Setiap pemain mendapat tepat satu giliran sebagai pemain aktif.

## 6. Pertanyaan

### 6.1 Bentuk data

Karena jawaban berupa teks bebas, bank pertanyaan tidak menyimpan pilihan jawaban.

```python
QUESTIONS = [
    {
        "id": "absurd_001",
        "category": "absurd",
        "text": "Kalau {subject} mendadak jadi penjahat super, kejahatan receh apa yang paling mungkin dilakukan?",
    },
]
```

Kriteria:

- ID unik dan stabil.
- Teks tidak kosong.
- Mendukung placeholder `{subject}` bila diperlukan.
- Menarik, ringan, dan berpotensi memunculkan jawaban lucu.
- Tidak meminta data sensitif.
- Tidak mendorong penghinaan, body shaming, konflik, pelecehan, atau pembukaan rahasia pribadi.
- Tidak mengandung jawaban yang objektif tunggal; pemain aktif tetap menjadi penilai.

Target jumlah:

```text
Development : minimal 60 pertanyaan
Production  : minimal 200 pertanyaan
Ditawarkan  : 5 pertanyaan per giliran
```

### 6.2 Kategori

```text
absurd
kebiasaan
makanan
perjalanan
khayalan
situasi_sosial
pilihan_sulit
masa_depan
benda
hiburan
```

Pemilihan lima soal sebaiknya mengambil beberapa kategori berbeda agar paket tidak terasa monoton.

### 6.3 Contoh pertanyaan awal

1. Kalau `{subject}` mendadak jadi penjahat super, kejahatan receh apa yang paling mungkin dilakukan?
2. Kalau `{subject}` bisa teleport sekarang juga, tempat pertama yang akan didatangi di mana?
3. Barang paling tidak penting apa yang kemungkinan besar selalu dibawa `{subject}`?
4. Kalau hidup `{subject}` jadi judul sinetron, judulnya apa?
5. Makanan apa yang masih sanggup dimakan `{subject}` tiga hari berturut-turut?
6. Kalau `{subject}` mendapat sepuluh juta rupiah tetapi harus habis hari ini, pembelian pertamanya apa?
7. Alasan terlambat paling masuk akal yang mungkin dipakai `{subject}` apa?
8. Kalau `{subject}` berubah jadi hewan selama sehari, hewan apa yang paling cocok?
9. Pekerjaan aneh apa yang diam-diam mungkin cocok untuk `{subject}`?
10. Kalau `{subject}` membuka warung, warung apa yang paling mungkin dibuat?
11. Lagu apa yang paling cocok diputar ketika `{subject}` masuk ruangan?
12. Kalau ada tombol untuk menghapus satu pekerjaan rumah selamanya, apa yang dipilih `{subject}`?
13. Superpower yang paling mungkin disalahgunakan `{subject}` untuk hal receh apa?
14. Kalau `{subject}` harus hidup di satu aplikasi selama seminggu, aplikasi apa?
15. Oleh-oleh paling aneh apa yang mungkin dibeli `{subject}` saat liburan?
16. Kalau `{subject}` jadi guru, pelajaran apa yang akan diajarkan dengan cara paling kacau?
20. Hal kecil apa yang paling mudah membuat `{subject}` bahagia?
21. Kalau `{subject}` punya robot asisten, tugas pertama yang diberikan apa?
22. Nama kapal bajak laut milik `{subject}` kira-kira apa?
23. Kalau `{subject}` ikut acara reality show, alasan terkenalnya apa?
24. Benda apa yang paling mungkin diberi nama oleh `{subject}`?
25. Kalau `{subject}` bisa mengganti suara notifikasi semua orang, suara apa yang dipilih?
26. Kalau `{subject}` harus mengenakan satu warna selama sebulan, warna apa?
27. Kalimat apa yang paling mungkin dikatakan `{subject}` saat panik?

Daftar contoh ini menjadi seed awal. Bank production tetap perlu peninjauan manual dan test validasi.

## 7. Timer dan kebijakan tidak merespons

Konstanta awal:

```python
QUESTION_PICK_TIMEOUT_SECONDS = 60
ANSWER_TIMEOUT_SECONDS = 120
JUDGING_TIMEOUT_SECONDS = 120
MESSAGE_PAUSE_SECONDS = 2
REVEAL_MIN_SECONDS = 2
REVEAL_MAX_SECONDS = 4
EDIT_RETRY_DELAYS = (0, 0.5, 1.5)
```

Gunakan timer bernama:

```text
question-<round>-<version>
answer-<round>-<version>
judge-<round>-<version>
```

### 7.1 Pemain aktif tidak memilih soal

- Giliran dilewati.
- Tidak ada poin internal pada ronde tersebut.
- `subject_pick_timeouts` pemain bertambah.
- Tambahkan satu AFK strike.
- Lanjutkan ke pemain berikutnya.

### 7.2 Pemain tidak mengonfirmasi jawaban

- Draft yang belum dikonfirmasi tidak dihitung.
- Pemain mendapat nol pada ronde itu.
- `missed_answer_rounds` bertambah.
- Permainan tetap lanjut.

### 7.3 Pemain aktif tidak menyelesaikan penilaian

Karena jawaban benar tidak dapat ditentukan otomatis:

- Giliran dibatalkan tanpa poin internal untuk semua pemain.
- Jawaban tidak diproses ke skor benar.
- `judge_timeouts` pemain aktif bertambah.
- Tambahkan satu AFK strike.
- Lanjutkan ke pemain berikutnya.

### 7.4 Penetapan AFK

Seorang pemain dianggap AFK untuk penghitungan leaderboard jika salah satu kondisi terpenuhi:

```text
- tidak melakukan satu pun aksi valid selama sesi; atau
- gagal pada giliran aktifnya dan melewatkan minimal separuh kesempatan menjawab; atau
- memiliki minimal 2 AFK strike.
```

Status dan statistik final harus konsisten serta dapat diuji. Jangan mengeluarkan pemain dari antrean hanya karena satu jawaban terlewat.

## 8. Struktur folder

```text
app/modules/games/implementations/kuis_kenal/
├── __init__.py
├── metadata.py
├── questions.py
├── state.py
├── keyboards.py
├── texts.py
└── game.py
```

Prasyarat routing privat generik:

```text
app/modules/games/
├── private_input.py
└── handlers/
    └── private_game_messages.py
```

Pengujian:

```text
tests/modules/games/implementations/kuis_kenal/
├── test_questions.py
├── test_state.py
├── test_question_selection.py
├── test_private_answers.py
├── test_answer_confirmation.py
├── test_judging.py
├── test_timeouts.py
├── test_stale_interactions.py
├── test_telegram_fallback.py
├── test_scores.py
├── test_recovery_policy.py
├── test_concurrency.py
└── test_full_game.py
```

Pengujian jembatan privat:

```text
tests/modules/games/
└── test_private_input.py
```

## 9. Tanggung jawab file implementasi

### 9.1 `metadata.py`

Berisi `GameMetadata` dan seluruh konstanta waktu, batas jawaban, jumlah soal yang ditawarkan, retry, dan pacing.

```python
QUESTION_OPTIONS_PER_TURN = 5
QUESTION_REROLL_LIMIT = 1
ANSWER_MAX_LENGTH = 300
```

Tidak boleh ada angka konfigurasi yang tersebar sebagai magic number di `game.py`.

### 9.2 `questions.py`

Berisi:

```python
QUESTIONS
get_question(question_id)
draw_question_options(...)
validate_question_bank()
```

`draw_question_options()` harus:

- Menghindari pertanyaan yang sudah digunakan.
- Mengusahakan variasi kategori.
- Deterministik bila diberi random seed dalam test.
- Mengembalikan tepat lima soal selama bank masih cukup.

### 9.3 `state.py`

Berisi fungsi murni:

```python
build_initial_state(...)
begin_turn(...)
offer_questions(...)
select_question(...)
reroll_questions(...)
store_answer_draft(...)
confirm_answer(...)
clear_answer_draft(...)
all_expected_answers_confirmed(...)
build_answer_groups(...)
toggle_answer_group(...)
resolve_turn(...)
advance_turn(...)
is_game_complete(...)
build_result_payload(...)
calculate_afk_flags(...)
```

Fungsi tidak mengakses database atau Telegram.

### 9.4 `keyboards.py`

Builder minimum:

```python
build_group_choose_question_link(...)
build_private_question_keyboard(...)
build_group_answer_link(...)
build_answer_confirmation_keyboard(...)
build_judging_keyboard(...)
build_zero_correct_confirmation_keyboard(...)
```

Semua callback memakai `GameCallback` dan separator internal selain `:`.

### 9.5 `texts.py`

Fungsi minimum:

```python
mention(...)
render_welcome(...)
render_turn_start(...)
render_question_options(...)
render_public_question(...)
render_private_answer_prompt(...)
render_answer_confirmation(...)
render_answer_recorded(...)
render_waiting_for_players(...)
render_judging(...)
render_turn_result(...)
render_scoreboard(...)
render_final_result(...)
render_timeout(...)
render_stale_interaction(...)
```

Nama user wajib di-escape:

```python
from html import escape


def mention(player: PlayerInfo) -> str:
    name = escape(player.display_name)
    return f'<a href="tg://user?id={player.telegram_user_id}">{name}</a>'
```

Jawaban pemain juga wajib di-escape sebelum dimasukkan ke pesan HTML.

### 9.6 `game.py`

Class:

```python
class KuisKenalGame(BaseGame):
    metadata = METADATA
```

Method wajib:

```python
initialize()
start()
handle_message()
handle_callback()
handle_timeout()
finish()
calculate_scores()
```

Helper yang disarankan:

```python
_save_state(...)
_begin_turn(...)
_open_question_selection(...)
_handle_question_pick(...)
_handle_question_reroll(...)
_begin_answering(...)
_handle_private_answer_text(...)
_handle_answer_confirm(...)
_handle_answer_change(...)
_begin_judging(...)
_handle_judgement_toggle(...)
_handle_judgement_done(...)
_resolve_turn(...)
_advance_or_finish(...)
_edit_with_fallback(...)
_close_message(...)
_get_player_map(...)
```

`restore()` tetap memakai default `NotImplementedError` karena sesi `RUNNING` tidak dilanjutkan setelah restart.

## 10. Bentuk `state_json`

```python
{
    "schema_version": 1,

    "phase": "question_select",
    "round": 1,
    "message_version": 1,

    "turn_queue": [11, 14, 18],
    "current_subject_id": 11,

    "offered_question_ids": [
        "absurd_001",
        "food_004",
        "habit_012",
        "travel_003",
        "social_008"
    ],
    "used_question_ids": [],
    "selected_question_id": None,
    "question_reroll_count": 0,

    "answer_nonce": "a8f20c1d",
    "judge_nonce": "0d93ab41",

    "answer_drafts": {
        "14": {
            "text": "Kabur ke warung",
            "revision": 2,
            "updated_at": "..."
        }
    },
    "final_answers": {
        "14": {
            "text": "Kabur ke warung",
            "revision": 2,
            "confirmed_at": "..."
        }
    },

    "answer_groups": [
        {
            "group_id": 1,
            "normalized_text": "kabur ke warung",
            "display_text": "Kabur ke warung",
            "user_ids": [14, 18],
            "is_correct": True
        }
    ],

    "scores": {
        "11": 0,
        "14": 2,
        "18": 1
    },

    "activity": {
        "11": {
            "valid_actions": 1,
            "answers_confirmed": 0,
            "correct_answers": 0,
            "subject_turns_completed": 1,
            "missed_answer_rounds": 0,
            "subject_pick_timeouts": 0,
            "judge_timeouts": 0,
            "afk_strikes": 0
        }
    },

    "public_message_id": None,
    "subject_private_message_id": None,
    "answer_confirmation_message_ids": {
        "14": 12345
    },

    "phase_started_at": None,
    "turn_started_at": None
}
```

Ketentuan:

- Key user ID dalam object JSON disimpan sebagai string.
- `turn_queue` menyimpan giliran yang belum dimulai.
- `current_subject_id` tidak ikut menjawab pada rondenya sendiri.
- `message_version` naik setiap tampilan interaktif diganti.
- Draft tidak dihitung sampai dikonfirmasi.
- Teks asli disimpan; teks normalisasi hanya untuk grouping.
- Pointer message ID dipakai untuk menolak callback dari pesan yang bukan lagi otoritatif.

## 11. Fase internal

```text
question_select
answering
judging
resolving
finished
```

Transisi valid:

```text
question_select → answering
question_select → resolving   # timeout pemain aktif
answering       → judging
judging         → resolving
judging         → resolving   # timeout, ronde tanpa poin
resolving       → question_select
resolving       → finished
```

Semua handler wajib memeriksa fase sebelum mengubah state.

## 12. Penyimpanan state

Gunakan satu helper:

```python
from sqlalchemy.orm.attributes import flag_modified


def _save_state(context: GameContext, state: dict) -> None:
    context.game_session.state_json = state
    flag_modified(context.game_session, "state_json")
```

Aturan:

- Setiap mutasi diikuti `_save_state()`.
- Gunakan `flush()` ketika perubahan harus terlihat di transaksi aktif.
- Gunakan `commit()` saat fallback Telegram menghasilkan pointer pesan otoritatif baru atau ketika alur timer memerlukan persistensi sebelum keluar.
- Jangan menyimpan `GameContext` atau `db_session` lintas callback/timer.

## 13. Callback dan validasi interaksi

Format callback ringkas:

```text
{round}-{version}-{action}-{value}
```

Action:

```text
qp   → pilih pertanyaan
qr   → ambil paket pertanyaan baru
ac   → konfirmasi jawaban
ae   → ubah jawaban
jt   → toggle kelompok jawaban benar/salah
jd   → selesai menilai
```

Contoh:

```text
1-2-qp-4
1-4-ac-2
1-6-jt-3
1-6-jd-0
```

Urutan validasi callback:

1. Parse `GameCallback`.
2. Pastikan format data valid.
3. Ambil `user_id = context.acting_user_id`.
4. Pastikan user peserta sesi.
5. Pastikan nomor ronde sesuai.
6. Pastikan versi sesuai.
7. Pastikan callback berasal dari message ID otoritatif untuk user/fase tersebut jika pointer tersedia.
8. Pastikan action sesuai fase.
9. Pastikan user berhak melakukan action.
10. Pastikan value valid.

Jangan memakai `callback.from_user.id` untuk identitas game.

## 14. Validasi jawaban teks

Saat `handle_message()` menerima pesan privat yang sudah dirutekan:

- Pastikan konteks privat masih aktif.
- Pastikan sesi masih `RUNNING`.
- Pastikan ronde, nonce, dan fase masih sesuai.
- Pastikan pengirim bukan pemain aktif.
- Terima hanya pesan teks biasa.
- Tolak string kosong setelah trim.
- Batas panjang awal 300 karakter.
- Tolak command sebagai jawaban.
- Simpan satu draft terbaru per pemain.
- Escape hanya saat render; jangan menyimpan string yang sudah di-escape.

Pesan privat tanpa konteks aktif mendapat petunjuk untuk menekan tombol `Jawab Privat` pada pesan game terbaru.

## 15. Ketahanan panggilan Telegram

Semua edit pesan interaktif memakai retry dan fallback:

1. Coba segera.
2. Ulangi setelah 0,5 detik.
3. Ulangi setelah 1,5 detik.
4. Jika tetap gagal, kirim pesan baru.
5. Simpan message ID baru sebagai pointer otoritatif.
6. Tolak callback dari pesan lama.

Pointer dipisahkan berdasarkan tujuan:

```text
public_message_id
subject_private_message_id
answer_confirmation_message_ids[user_id]
```

Pesan lama ditutup sebisa mungkin, tetapi state dan validasi callback tetap menjadi sumber kebenaran jika edit penutupan gagal.

## 16. Pacing

Alur yang mengirim beberapa pesan berturut-turut diberi jeda pendek.

Contoh:

```text
hasil giliran
    → jeda 2 detik
    → klasemen sementara
    → jeda 2 detik
    → pengumuman pemain aktif berikutnya
```

Timer baru dijadwalkan setelah tombol interaktif benar-benar tampil.

## 17. Skor internal permainan

Skor sesi untuk menentukan pemenang:

```text
Jawaban ditandai benar : +1
Jawaban salah           :  0
Tidak menjawab          :  0
Pemain aktif            : tidak mendapat poin pada giliran sendiri
```

Pemenang:

- Skor internal tertinggi menang.
- Jika satu pemain tertinggi, isi `winner_user_id`.
- Jika beberapa pemain seri, `winner_user_id=None` dan simpan seluruh pemenang pada `payload["winner_user_ids"]`.

Tidak ada tie-breaker pada versi pertama.

## 18. Skor leaderboard bulanan

### 18.1 Prinsip fairness

Skor leaderboard harus:

- Memberi skor dasar kepada pemain yang benar-benar berpartisipasi.
- Menghargai setiap jawaban final, bukan hanya jawaban benar.
- Menghargai tugas pemain aktif yang memilih soal dan menyelesaikan penilaian.
- Memberi tambahan karena akurasi.
- Tidak memberi bonus pemenang terpisah agar kemampuan yang sama tidak dihitung dua kali.
- Mendekati baseline sekitar 36 poin per menit pada pemain aktif rata-rata.
- Memberi penalti parsial kepada pemain AFK, bukan menghapus seluruh progres yang sudah dilakukan.

### 18.2 Formula awal

```text
participation_score = 10 jika pemain melakukan minimal satu aksi valid
participation_score = 0  jika tidak melakukan aksi valid

survival_score =
    36 × jumlah jawaban yang dikonfirmasi
  + 44 × jumlah giliran pemain aktif yang selesai dinilai

result_score =
    36 × jumlah jawaban yang ditandai benar

final_score = participation_score + survival_score + result_score
```

`survival_score` pada game ini bermakna progres aktif sepanjang sesi, bukan eliminasi.

Kalibrasi awal didasarkan pada asumsi:

- Satu giliran rata-rata sekitar 90 detik.
- Pemain aktif penuh melakukan satu aksi per ronde: menjawab pada `N-1` ronde dan menjalankan satu giliran sendiri.
- Tingkat jawaban benar rata-rata sekitar 50%.

Untuk `N` pemain aktif penuh:

```text
10 + 44 + 36(N-1) + 36 × 0,5(N-1)
= 54N poin
```

Jika sesi berlangsung sekitar `1,5N` menit:

```text
54N ÷ 1,5N = 36 poin/menit
```

### 18.3 Penalti AFK

Untuk pemain yang diklasifikasikan AFK:

```text
participation_score = 0
survival_score      = floor(raw_survival_score × 0,5)
result_score        = floor(raw_result_score × 0,5)
final_score         = jumlah ketiganya
```

Progress sebelum menjadi tidak aktif tetap dihargai separuh.

### 18.4 Kalibrasi setelah testing nyata

Formula di atas adalah titik awal, bukan angka final tanpa pengujian.

Setelah minimal 10 sesi nyata dengan ukuran lobby berbeda:

1. Ambil `started_at` dan `finished_at`.
2. Hitung `final_score ÷ durasi_menit` untuk setiap pemain aktif.
3. Pisahkan pemain aktif penuh dan AFK.
4. Targetkan rata-rata pemain aktif penuh sekitar 36 poin/menit.
5. Targetkan pemain AFK sekitar separuh laju aktif penuh.
6. Ubah konstanta `36` dan `44` bila laju terlalu tinggi atau rendah.
7. Simpan hasil kalibrasi dalam catatan test agar keputusan angka dapat dilacak.

### 18.5 Implementasi

```python
async def calculate_scores(
    self,
    context: GameContext,
    result: GameResult,
) -> dict[int, ScoreBreakdown]:
    ...
```

Data diambil dari `state_json["activity"]` dan semua player sesi. Commit ke `user_game_scores` tetap dilakukan secara idempoten oleh `GameManager.finish_game()`.

## 19. `GameResult`

Payload minimum:

```python
GameResult(
    winner_user_id=single_winner_id,
    summary="Galih menang dengan 4 jawaban benar.",
    payload={
        "rounds": 5,
        "scores": {
            "11": 4,
            "14": 3,
            "18": 2,
        },
        "winner_user_ids": [11],
        "activity": {...},
    },
)
```

Ajakan main lagi dan petunjuk `/skor` tidak dikirim dari game karena sudah ditangani engine.

## 20. Restart dan recovery

Kebijakan mengikuti engine yang tersedia:

### LOBBY dan STARTING

- Engine menjadwalkan ulang timer jika belum kedaluwarsa.
- Engine langsung mengeksekusi timeout yang sudah lewat.
- Game tidak menambah mekanisme recovery sendiri.

### RUNNING

- Sesi di-abort oleh recovery engine.
- Grup menerima notifikasi bahwa game dihentikan karena restart.
- Giliran, draft jawaban, konteks privat, dan timer tidak dipulihkan.
- `restore()` tetap `NotImplementedError`.
- Deep link dan callback lama ditolak karena sesi tidak lagi aktif.
- `PrivateInputRegistry` dikosongkan saat startup.
- Skor leaderboard tidak dikomit karena sesi tidak selesai melalui `finish_game()`.

Game tidak mencoba melanjutkan ronde setengah jalan.

## 21. Concurrency dan idempotensi

Satu lock per session dari engine menjadi satu-satunya lock game.

Skenario yang wajib aman:

- Dua pemain mengirim jawaban hampir bersamaan.
- Pesan teks kedua tiba ketika callback konfirmasi pertama sedang diproses.
- Semua jawaban selesai bersamaan dengan timeout answer.
- Pemain aktif menekan selesai menilai bersamaan dengan timeout judge.
- Callback `Selesai Menilai` ditekan dua kali.
- `finish_game()` terpicu lebih dari sekali.

Proteksi:

- Validasi fase, ronde, versi, dan pointer message.
- `resolving` menjadi guard sebelum skor diubah.
- Simpan penanda `resolved_rounds` atau `last_resolved_round`.
- Fungsi resolve harus idempoten.
- Skor leaderboard tetap terlindungi idempotensi engine.

## 22. Registrasi

Satu perubahan integrasi:

```python
from app.modules.games.implementations.kuis_kenal.game import KuisKenalGame


def create_game_registry(settings: Settings) -> GameRegistry:
    registry = GameRegistry()
    registry.register(KuisKenalGame())
    return registry
```

Selama development dapat dibungkus kondisi non-production sampai test manual selesai.

Jembatan input privat didaftarkan sebagai handler generik modul games, bukan sebagai handler khusus key `kuis_kenal`.

## 23. Tahapan implementasi

### Tahap 0 — Jembatan input privat generik

Pekerjaan:

- Implementasikan `PendingPrivateInput`.
- Implementasikan registry dan expiration.
- Implementasikan handler pesan privat generik.
- Hubungkan ke `GameManager` dan `BaseGame.handle_message()`.
- Tambahkan pembersihan saat sesi selesai, batal, abort, dan startup.

Kriteria selesai:

- Pesan privat dapat diarahkan ke sesi yang benar.
- User tanpa konteks tidak memengaruhi game.
- Dua sesi berbeda tidak tertukar.
- Restart menghapus seluruh konteks privat.

### Tahap 1 — Fondasi game

Pekerjaan:

- Buat folder dan file implementasi.
- Tambahkan metadata.
- Buat state awal dan `_save_state()`.
- Buat antrean giliran acak.
- Registrasikan game untuk development.

Kriteria selesai:

- Game muncul di `/game`.
- Lobby dan ready-check berjalan.
- Sesi masuk `RUNNING` dan state awal tersimpan.

### Tahap 2 — Bank pertanyaan

Pekerjaan:

- Tambahkan minimal 60 pertanyaan development.
- Tambahkan kategori.
- Implementasikan validasi bank.
- Implementasikan pemilihan lima soal lintas kategori.

Kriteria selesai:

- ID unik.
- Tidak ada pertanyaan kosong/sensitif.
- Lima soal tidak berulang dalam sesi selama stok cukup.

### Tahap 3 — Pemilihan soal privat

Pekerjaan:

- Deep link pemain aktif.
- Tampilan lima soal.
- Callback pilih/reroll.
- Timeout pemilihan.
- Proteksi link dan callback lama.

Kriteria selesai:

- Hanya pemain aktif dapat memilih.
- Pilihan tersimpan satu kali.
- Timeout tidak menghentikan sesi.

### Tahap 4 — Jawaban teks bebas

Pekerjaan:

- Deep link jawab.
- Aktivasi konteks privat.
- Validasi teks.
- Penyimpanan draft.
- Batas panjang dan escaping.

Kriteria selesai:

- Jawaban tidak masuk grup.
- Pemain aktif tidak dapat menjawab rondenya sendiri.
- Draft tidak dihitung sebagai jawaban final.

### Tahap 5 — Konfirmasi jawaban

Pekerjaan:

- Tombol Ya/Ubah.
- Revision counter.
- Pointer pesan konfirmasi per user.
- Penyelesaian lebih cepat saat semua final.

Kriteria selesai:

- Jawaban final tidak berubah.
- Callback revisi lama ditolak.
- Ubah jawaban mengaktifkan kembali input privat.

### Tahap 6 — Pemeriksaan jawaban

Pekerjaan:

- Grouping normalisasi.
- Tampilan anonim.
- Toggle benar/salah.
- Konfirmasi nol jawaban benar.
- Timeout penilaian.

Kriteria selesai:

- Hanya pemain aktif dapat menilai.
- Beberapa jawaban dapat benar.
- Timeout tidak memberi skor salah secara otomatis.

### Tahap 7 — Resolusi ronde dan hasil akhir

Pekerjaan:

- Skor internal.
- Hasil ronde.
- Klasemen sementara.
- Pergantian pemain aktif.
- Penanganan seri.
- `GameResult` dan `finish_game()`.

Kriteria selesai:

- Setiap pemain mendapat satu giliran.
- Skor tidak diproses dua kali.
- Game berakhir tepat satu kali.

### Tahap 8 — Skor leaderboard

Pekerjaan:

- Catat statistik aktivitas lengkap.
- Implementasikan AFK classifier.
- Implementasikan `calculate_scores()`.
- Test idempotensi dan formula.

Kriteria selesai:

- Pemain aktif mendapat partisipasi.
- Jawaban final dan akurasi dihargai.
- AFK mendapat penalti parsial.
- Tidak ada winner bonus ganda.

### Tahap 9 — Hardening Telegram

Pekerjaan:

- Retry/fallback seluruh edit interaktif.
- Pesan otoritatif per konteks.
- Penutupan keyboard lama.
- Pacing dan timer setelah reveal.

Kriteria selesai:

- Gagal edit tidak membuat game macet.
- Dua pesan aktif tidak dapat sama-sama mengubah state.

### Tahap 10 — Test otomatis

Skenario wajib:

1. Tiga pemain menyelesaikan game normal.
2. Sepuluh pemain menyelesaikan game normal.
3. Pemain aktif memilih salah satu dari lima soal.
4. Reroll soal sesuai batas.
5. User bukan pemain membuka deep link.
6. Pemain aktif membuka link jawab.
7. Jawaban kosong, command, non-teks, dan terlalu panjang ditolak.
8. Pemain mengirim draft lalu mengubahnya.
9. Draft tanpa konfirmasi tidak dihitung.
10. Semua pemain mengonfirmasi sebelum timeout.
11. Sebagian pemain tidak menjawab.
12. Pemain aktif timeout memilih soal.
13. Pemain aktif timeout menilai.
14. Beberapa kelompok jawaban ditandai benar.
15. Tidak ada jawaban benar diselesaikan langsung melalui tombol `TIDAK ADA YANG BENAR`.
16. Caption tombol berubah dari `TIDAK ADA YANG BENAR` menjadi `✅ Selesai Menilai` saat pilihan benar pertama ditandai, dan kembali lagi bila semua tanda benar dilepas.
17. Hasil ronde menyebut semua pemain dengan mention beserta jawaban masing-masing.
18. Pemain tanpa jawaban ditampilkan sebagai `Tidak menjawab` pada daftar pemain yang tidak berhasil.
19. Pesan skor dikirim terpisah setelah pesan hasil ronde.
20. Callback ronde lama ditekan.
21. Callback dari pesan non-otoritatif ditekan.
22. Deep link lama dibuka.
23. Edit Telegram gagal tiga kali lalu fallback.
24. Timeout dan callback terakhir terjadi bersamaan.
25. Dua jawaban privat masuk bersamaan.
26. Resolve ronde dipanggil dua kali.
27. Hasil akhir seri.
28. Hasil akhir pemenang tunggal.
29. Formula leaderboard pemain aktif.
30. Formula leaderboard AFK.
31. `finish_game()` dua kali tidak menggandakan skor.
32. Restart saat LOBBY/STARTING mengikuti recovery engine.
33. Restart saat RUNNING menghasilkan abort tanpa skor leaderboard.
34. Konteks privat dibersihkan saat game berakhir atau abort.

Gunakan `FakeBot`, SQLite file sungguhan, dan `asyncio.gather` untuk test konkurensi.

### Tahap 11 — Test Telegram nyata

Gunakan persona `/p1` sampai `/p7`.

Periksa:

- Deep link membuka konteks yang benar.
- Bot dapat mengirim pesan privat setelah user membuka bot.
- Jawaban tidak bocor ke grup.
- Konfirmasi nyaman digunakan.
- Penilaian anonim mudah dipahami.
- Timer cukup panjang untuk mengetik.
- Mention dan HTML tidak rusak.
- Pacing tidak terlalu cepat atau terlalu lambat.
- Sesi tetap selesai ketika beberapa pemain diam.

### Tahap 12 — Kalibrasi dan production

Sebelum production:

- Bank pertanyaan minimal 200.
- Review keamanan dan sensitivitas pertanyaan selesai.
- Minimal 10 sesi nyata dipakai untuk kalibrasi poin/menit.
- Rata-rata skor pemain aktif mendekati baseline lintas-game.
- Seluruh test otomatis lulus.
- Minimal tiga sesi Telegram lengkap tanpa intervensi developer.
- Registrasi non-production dihapus.

## 24. Ruang lingkup versi pertama

Termasuk:

- Antrean giliran acak.
- Lima pilihan pertanyaan per pemain aktif.
- Jawaban teks bebas melalui chat privat.
- Konfirmasi masing-masing jawaban.
- Pemeriksaan anonim oleh pemain aktif.
- Beberapa jawaban dapat dinyatakan benar.
- Timer setiap fase.
- Skor internal dan leaderboard bulanan.
- Seri.
- Retry/fallback Telegram.
- Proteksi interaksi lama.
- Recovery mengikuti engine: sesi `RUNNING` di-abort.

Belum termasuk:

- Resume ronde setelah restart.
- Pertanyaan buatan pemain.
- Jawaban berupa foto, voice note, sticker, atau media lain.
- Voting publik untuk menentukan jawaban benar.
- Mode tim.
- Tie-breaker.
- Riwayat leaderboard all-time.

## 25. Definition of Done

Implementasi dinyatakan selesai jika:

- Seluruh alur dari lobby sampai skor akhir berjalan tanpa perubahan manual database.
- Semua jawaban teks dikirim dan dikonfirmasi lewat chat privat.
- Pemain aktif dapat memilih satu dari lima soal dan menilai jawaban.
- Permainan tidak macet ketika ada pemain diam.
- Callback, deep link, timer, dan pesan lama tidak dapat merusak state aktif.
- Mutasi `state_json` selalu tersimpan dengan `flag_modified`.
- Skor ronde idempoten.
- Skor leaderboard idempoten dan terkalibrasi.
- Restart saat `RUNNING` menghasilkan abort bersih tanpa commit skor.
- Seluruh test otomatis dan test Telegram nyata lulus.
