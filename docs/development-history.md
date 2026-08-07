# Riwayat Pengembangan

Kronologi keputusan penting dan **bug nyata yang ditemukan lewat testing** (bukan cuma dibaca kodenya) selama membangun project ini. Ini dirujuk dari beberapa tempat di `game-development-guide.md` sebagai "lihat riwayat pengembangan" — jadi kalau kamu baca referensi itu, ini dokumennya.

Ditulis per milestone, bukan per hari. Untuk status TERKINI (bukan histori), lihat [`project-status.md`](project-status.md).

---

## Fase 1 — Fondasi bot

**Dibangun**: `app/main.py`/`bootstrap.py`, config (`.env` via `python-dotenv`), logging ke `logs/app.log`, `/start` `/help` di modul `common`.

**Keputusan**: Python venv pakai 3.10.11 (yang tersedia di `PATH`), bukan versi lebih baru yang juga terinstal (3.14 via `py` launcher). Konsekuensi: `enum.StrEnum` (dicontohkan di blueprint §7.3) **tidak tersedia** — semua enum di project ini pakai pola `class X(str, Enum)` sebagai gantinya.

**Bug ditemukan**: `app/main.py` tidak pernah menutup `bot.session` (koneksi HTTP aiogram) saat shutdown/error — cuma `engine.dispose()` untuk database. Diperbaiki dengan `async with bot:` (aiogram menyediakan `__aexit__` yang menutup session otomatis).

---

## Fase 1 (lanjutan) — Database & tracking

**Dibangun**: SQLAlchemy async engine + `aiosqlite`, PRAGMA WAL/foreign_keys/busy_timeout/synchronous, Alembic, model `User`/`Group`/`GroupMember`, middleware `DatabaseMiddleware`/`UserTrackingMiddleware`/`GroupTrackingMiddleware`.

**Bug ditemukan (penting)**: SQLite **membuang info timezone** setiap kali datetime dibaca ulang dari sesi database baru — walau yang disimpan adalah `datetime.now(timezone.utc)` (aware). Kalau ada kode yang menghitung selisih waktu antara nilai yang baru dibaca (naive) dan `datetime.now(timezone.utc)` (aware), Python melempar `TypeError: can't subtract offset-naive and offset-aware datetimes`.

**Perbaikan**: seluruh project distandarkan ke **naive-UTC** lewat `app/utils/datetime.py::utcnow()` — dipakai konsisten di semua repository dan service, tidak ada lagi `datetime.now(timezone.utc)` manual di tempat lain.

**Riset dilakukan**: dicek juga kecocokan SQLite WAL mode dengan Termux (target deployment) — WAL butuh filesystem lokal yang mendukung locking/mmap normal. Private storage Termux (`$HOME/apps/...`) aman; **shared storage (`/sdcard`) TIDAK aman** untuk WAL (sering FUSE-mounted, locking tidak reliable). Selama path database tetap di private storage (default blueprint sudah begitu), tidak ada masalah.

---

## Fase 2 — Admin monitoring

**Dibangun bertahap**: `/health` dulu (paling sederhana, buat uji middleware admin end-to-end) → lalu `/users`/`/user`/`/groups`/`/group` dengan pagination → lalu `/admin` dashboard dengan tombol inline.

**Perluasan arsitektur**: dashboard butuh tombol, artinya middleware (`Database`, `UserTracking`, `AdminContext`, `GroupTracking`) yang sebelumnya cuma jalan di observer `message` harus diperluas ke `callback_query` juga. Ini butuh `app/utils/telegram.py::extract_chat()` — helper yang tahu cara ambil `chat` dari `Message` ATAU `CallbackQuery` (struktur beda: `CallbackQuery` tidak punya `.chat` langsung, cuma `.message.chat`).

**Keputusan yang disengaja**: banyak kolom/tabel dari blueprint (`administrators.permissions_json`, `game_players.score`, dst) **sengaja tidak dibuat** di fase ini karena belum ada fitur yang memakainya — prinsip "jangan bangun yang belum ada konsumennya".

---

## Fase 3 — Game engine + game pertama ("Kursi Kosong" versi awal, sekarang "Test")

**Konteks keputusan game**: blueprint tidak menentukan aturan main game pertama (cuma bilang "buat menguji game engine"). Disepakati bareng user: game musical-chairs sederhana — tiap ronde kursi = pemain hidup − 1, tepat 1 tereliminasi per ronde (kalau ada yang tidak klik apapun, sisa kursi diisi ACAK dari yang belum pilih, supaya invarian "tepat 1 eliminasi" selalu terjaga meski ada yang pasif).

**Bug ditemukan #1 — mutasi JSON tidak terdeteksi SQLAlchemy**: kolom `state_json` di-mutasi in-place (`state["round"] += 1`) lalu di-assign balik ke objek yang SAMA (`obj.state_json = state`) — SQLAlchemy tidak menganggap ini sebagai perubahan (objek python-nya identik), jadi TIDAK PERNAH benar-benar tersimpan ke database. Perbaikan: wajib panggil `flag_modified(obj, "state_json")` setiap kali. Sudah dibungkus jadi helper `_save_state()` di implementasi game supaya tidak lupa.

**Bug ditemukan #2 — race condition / lost update**: kalau dua request (dua klik tombol beda pemain) berebut lock yang sama, dan COMMIT terjadi di LUAR critical section (misal di middleware, setelah lock dilepas), request kedua bisa membaca data BASI sebelum request pertama benar-benar commit — menimpa balik perubahan request pertama. Perbaikan: commit dilakukan **di dalam** `async with lock:`, sebelum lock dilepas, untuk operasi yang memutasi state bersama (`join_game`, `handle_callback`, dst).

**Diverifikasi lewat test konkurensi nyata** (bukan cuma baca kode): dua "pemain" (session database terpisah, mensimulasikan dua update Telegram berbeda) menekan **kursi yang sama** lewat `asyncio.gather` — tepat 1 yang berhasil, bukan 0 atau 2. Pola test ini (SQLite file asli, bukan `:memory:`, + `FakeBot` pencatat teks, + `asyncio.gather`) jadi standar verifikasi untuk semua fitur game selanjutnya.

---

## Testing solo — sistem persona (`/p1`-`/p7`)

**Masalah**: game butuh multi-pemain, developer solo tidak punya teman untuk tes. Opsi yang dipilih (dari beberapa alternatif yang dibahas): admin bisa "berperan" jadi virtual player lewat command, lalu SEMUA aksi berikutnya (termasuk klik tombol Telegram SUNGGUHAN) tercatat sebagai virtual player itu — bukan simulasi/script, benar-benar lewat jalur aiogram normal.

**Jebakan desain yang dicegah dari awal**: kalau `PersonaMiddleware` menukar `current_user` SEBELUM `AdminContextMiddleware` menghitung `admin_role`, maka begitu admin jadi persona pertama, `admin_role` ikut jadi milik virtual player (bukan admin) — admin jadi TERKUNCI, tidak bisa lagi kirim `/p2` atau `/p0` untuk kembali. Perbaikan: command switch-persona selalu pakai `real_admin_role` (dihitung dari identitas ASLI, disuntik terpisah oleh `PersonaMiddleware`), bukan `admin_role` yang bisa saja sudah tertukar.

**Detail implementasi penting**: `PersonaMiddleware` harus jadi **satu instance yang dibagi** antara observer `message` dan `callback_query` (bukan dibuat ulang per observer seperti middleware lain yang stateless) — karena switch lewat command (message) harus terlihat oleh klik tombol (callback_query) berikutnya.

---

## Redesain alur lobby (extend + ready-check)

**Perubahan besar dari blueprint**: blueprint asli (§13) mengusulkan "begitu minimum pemain tercapai → countdown 5 detik → mulai". Diganti total (permintaan eksplisit user) dengan:
- Lobby fixed 60 detik, bisa di-**Extend** tanpa batas oleh siapapun yang sudah join (reset ke 60 detik lagi).
- Setelah lobby tutup dengan pemain cukup → fase **ready-check**: mention semua pemain, tombol "✅ Siap", 60 detik lagi. Yang tidak klik siap di-**kick**, lalu game tetap lanjut kalau sisa masih cukup, atau batal kalau tidak.

**Bug ditemukan — self-cancellation timer (paling signifikan)**: laporan awal user "timer tidak otomatis jalan" (baik lobby-timeout maupun ready-check timeout). Root cause: saat timer habis dan memutuskan untuk `cancel_game()`, fungsi itu memanggil `cancel_session()` yang membatalkan SEMUA timer sesi itu — **termasuk timer yang sedang berjalan ITU SENDIRI** (task yang memanggil `cancel_game()`), karena task itu belum `done()`. Task jadi ter-cancel di tengah eksekusi, sebelum sempat commit perubahan status ke database — jadi TERLIHAT seperti "tidak terjadi apa-apa".

**Cara ditemukan**: semua test SEBELUMNYA memanggil logic timer secara LANGSUNG (memanggil fungsi Python-nya, bypass `asyncio.create_task`+`sleep` yang sesungguhnya) — jadi tidak pernah mengekspos bug ini. Begitu dibuat test yang benar-benar menjadwalkan via `asyncio.create_task` dan menunggu beberapa detik sungguhan, bug langsung kelihatan (`task.cancelled() == True`, seharusnya `False`).

**Perbaikan**: `TimerRegistry.cancel()` sekarang skip kalau target adalah `asyncio.current_task()` — biarkan selesai secara normal, jangan cancel diri sendiri.

**Bug ditemukan (kedua, terkait)**: `cancel_session()` mencocokkan key timer pakai `key.startswith(prefix)` — ini match SEBAGIAN STRING, jadi `"lobby:10"` ikut cocok sebagai prefix dari `"lobby:1"`. Kalau ada banyak sesi berjalan, membatalkan sesi #1 bisa salah ikut membatalkan timer sesi #10, #11, dst. Diperbaiki jadi pencocokan EXACT lewat `key.partition(":")`.

**Pelajaran umum**: kode yang HANYA diuji lewat pemanggilan fungsi langsung (tanpa lewat scheduler/task/lock yang sesungguhnya) bisa lolos test tapi tetap punya bug konkurensi nyata. Pola test yang benar untuk timer: jadwalkan lewat API publik yang sesungguhnya (`_schedule_lobby_timeout`, dst), lalu `await asyncio.sleep(N)`, baru cek hasilnya — jangan panggil `_resolve_xxx_timeout()` langsung kalau yang mau diuji justru soal *scheduling*-nya.

---

## Pesan yang lebih manusiawi

Setelah sistem lobby jalan, user minta kata-kata lebih ramah: minta maaf + mention pemain terdampak saat dibatalkan (beda kalimat untuk "kurang pemain di lobby" vs "kurang yang siap di ready-check"), dan selalu ada ajakan main lagi (`/game` polos sebagai teks biasa, supaya Telegram otomatis mengenalinya sebagai command yang bisa di-tap) di SETIAP jalur akhir game (menang atau batal) — diimplementasikan generik di `GameManager`, bukan diulang per-game.

---

## Pengerasan fondasi — error handler & recovery

**Dibangun**: `dispatcher.errors.register(...)` sebagai catch-all untuk exception tak tertangani (reference code + log ke `logs/error.log` baru + notifikasi ke superadmin), dan `GameManager.recover_sessions()` dipanggil sekali di startup sebelum polling — LOBBY/STARTING yang belum kedaluwarsa dijadwal ulang timernya (pakai sisa waktu yang benar), yang sudah kedaluwarsa langsung dieksekusi ulang, RUNNING di-**ABORT** (bukan resume mid-round — `BaseGame.restore()` sengaja masih `NotImplementedError`, sesuai kebijakan blueprint untuk versi awal).

---

## Rename & studi desain Kursi Kosong yang sesungguhnya

**Insiden kecil**: instruksi "ubah nama game simple_game jadi Test" awalnya disalahartikan sebagai rename STRUKTUR (folder+class), padahal maksudnya cuma ubah field `name`/`description` di metadata. Diperbaiki (revert folder yang salah dibuat, cuma edit metadata) sebelum lanjut.

**Ditambahkan**: `create_game_registry(settings)` sekarang cuma daftarkan game "Test" kalau `APP_ENV != "production"` — jadi hilang total (bukan cuma disembunyikan dari list) di production.

**Studi desain nyata**: file `GAME DESIGN - Kursi Kosong.docx` (dokumen desain resmi, jauh lebih detail dari game "Test" yang dibangun ad-hoc di Fase 3) dipelajari dan ditranskrip ke `game-design-kursi-kosong.md`. Ditemukan beberapa gap nyata antara desain itu dan engine yang ada:
- Engine cuma punya 1 slot timer per session — tidak cukup untuk jendela rebutan kursi per-kursi yang bisa jalan bersamaan.
- Game "Test" **tidak** memvalidasi nomor ronde di callback (bug nyata, belum diperbaiki karena game itu sudah frozen) — desain Kursi Kosong secara eksplisit merancang format callback untuk mencegah kasus persis ini.
- Belum ada status pemain `AFK` (beda konsekuensi skor dari `ELIMINATED` biasa).
- **Belum ada sistem skor/leaderboard lintas-game sama sekali** — gap paling besar, direkomendasikan dibangun generik di engine (bukan ditempel khusus 1 game) supaya game berikutnya tidak menabrak keputusan yang sama.

Ditulis jadi rencana implementasi 6 tahap di `kursi-kosong-implementation-plan.md` (Tahap 0 = kerjakan gap-gap di atas dulu, sebelum kode Kursi Kosong itu sendiri). **Belum ada satu baris kode Kursi Kosong yang ditulis** — sengaja, sesuai permintaan user ("jangan langsung membuat game kursi kosong").

**File sumber diarsipkan**: `Blueprint.docx` dan `GAME DESIGN - Kursi Kosong.docx` dipindah ke `archive/` (gitignored) setelah ditranskrip lengkap ke `docs/blueprint.md` dan `docs/game-design-kursi-kosong.md` — supaya `archive/` tidak perlu dibuka lagi.

---

## Wrap-up sesi & setup git

Ditutup dengan dokumentasi handoff: `README.md`, `docs/project-status.md`, `docs/development-history.md` (dokumen ini) dibuat supaya sesi/percakapan baru bisa lanjut tanpa baca ulang seluruh kode. Memory Claude Code juga diisi dengan ringkasan status + pelajaran penting (verifikasi lewat test nyata, jangan asumsikan scope luas dari instruksi ambigu).

User men-setup git sendiri (`git init`, commit pertama, remote `origin` → `github.com/galihjk/galihjkbot.git`, push ke `main`). Diverifikasi: `.env` dan folder `data/`/`logs/`/`archive/`/`.venv/` tidak ikut tertrack (sesuai `.gitignore` yang sudah disiapkan sebelumnya). 111 file masuk commit pertama. Histori SEBELUM titik ini (semua yang tercatat di dokumen ini) tidak ada di `git log` — cuma tercatat manual di sini.

---

## Kursi Kosong Tahap 0 — fondasi engine (multi-timer + `AFK`)

**Dibangun** (murni `engine/`, tidak menyentuh game "Test" ataupun kode Kursi Kosong): `GameManager.schedule_timer(session_id, name, delay)`/`cancel_timer(session_id, name)`, key `turn:{session_id}:{name}` — mengizinkan beberapa timer dalam-game jalan bersamaan per session (prasyarat jendela kontes kursi 1,2 detik per kursi di Kursi Kosong, yang bisa >1 kursi diperebutkan sekaligus dalam satu ronde). `schedule_turn_timeout`/`cancel_turn_timeout` lama jadi wrapper tipis (`name="round"`) supaya `simple_game` tidak perlu diubah sama sekali. Ditambah `GamePlayerStatus.AFK` (kolom `String`, tidak perlu migration).

**Bug yang sudah ketahuan sejak studi desain, diperbaiki di sini**: `TimerRegistry.cancel_session()` mem-parsing key timer dengan `key.partition(":")` lalu membandingkan bagian kedua PERSIS dengan `str(session_id)` — begitu key berubah jadi 3-bagian (`turn:5:chair-3`), bagian keduanya adalah `"5:chair-3"`, tidak akan pernah cocok dengan `"5"`, jadi timer per-kursi tidak akan ikut ter-cancel saat sesi dibatalkan/selesai (kebocoran timer). Diperbaiki dengan cek `rest == str(session_id) or rest.startswith(f"{session_id}:")` — cocok untuk key 2-bagian lama maupun 3-bagian baru.

**Diverifikasi lewat 3 integration test ad-hoc** (SQLite file asli, `FakeBot`, `asyncio.gather` untuk konkurensi — pola standar project ini, ditulis di scratchpad lalu dibuang setelah lolos, tidak masuk repo karena belum ada test suite formal):
1. `TimerRegistry` murni: dua timer beda `name` di session sama, dijadwalkan bersamaan, tetap jalan independen (tidak saling cancel seperti sebelum perbaikan); `cancel_session()` membatalkan keduanya sekaligus.
2. Lewat `GameManager` sungguhan (real DB session + FakeBot): `schedule_timer` dua nama berbeda pada session RUNNING yang sama, keduanya memicu `handle_timeout` dengan `timer_key` yang BISA dibedakan; `cancel_timer` satu nama tidak ikut membatalkan nama lain.
3. **Regresi penuh game "Test"** (3 pemain: lobby → join → ready-check → ronde dengan 2 pemain klik kursi yang SAMA lewat `asyncio.gather`, tepat 1 yang menang → ronde final → `FINISHED` dengan pemenang benar) — lolos tanpa perubahan perilaku, membuktikan wrapper `schedule_turn_timeout`/`cancel_turn_timeout` tidak mengubah apapun dari sudut pandang game yang sudah ada.

Item lain di Tahap 0 (konvensi validasi round di callback, skema tabel `user_game_scores`) sengaja **tidak diimplementasikan** di titik ini — cuma keputusan desain yang sudah disepakati di `kursi-kosong-implementation-plan.md`, kodenya menyusul di Tahap 1 dan Tahap 4. Tahap 1 (lobby → ronde dasar Kursi Kosong, kursi masih first-click-wins) adalah pekerjaan berikutnya.

---

## Kursi Kosong Tahap 1 — lobby → ronde dasar (kode game pertama, akhirnya)

**Dibangun**: `app/modules/games/implementations/kursi_kosong/` — folder pertama yang benar-benar berisi kode Kursi Kosong (sebelumnya cuma desain+rencana). Mengikuti pola `simple_game` (lihat `game-development-guide.md`) tapi dengan dua beda sengaja:
- **Validasi nomor ronde ada dari awal** di `handle_callback` — bukan bug yang dibiarkan seperti `simple_game`. `data` callback berisi `"{round_number}-{chair_number}"`, ditolak kalau `round_number` tidak cocok `state["round"]`.
- **Keyboard menampilkan SEMUA kursi** (bukan cuma yang kosong seperti `simple_game`), dengan nama pemain yang sudah duduk (dipotong maks. 10 karakter), dan di-refresh LIVE (`bot.edit_message_reply_markup`) tiap kali ada yang berhasil klaim kursi — sesuai desain §7. Kursi masih first-click-wins (belum ada jendela kontes 1,2 detik, itu Tahap 2).

**Bug baru ketahuan saat implementasi (bukan dari studi desain sebelumnya)**: contoh kode di `game-development-guide.md` §6 menyarankan encode `data` callback pakai separator `":"` (mis. `f"{round_number}:{action_data}"`). Ternyata `GameCallback.pack()` (dari `CallbackData` bawaan aiogram) **memakai `":"` sendiri** untuk memisahkan field (`session_id`, `data`) — kalau isi `data` juga mengandung `":"`, `pack()` langsung melempar `ValueError: Separator symbol ':' can not be used in value`. Baru ketahuan lewat test nyata (percobaan pertama `_begin_round` langsung crash), bukan dari baca kode. Diperbaiki dengan pakai `"-"` sebagai separator internal di dalam `data`, dan panduan (`game-development-guide.md` §6) diperbarui supaya game berikutnya tidak jatuh ke jebakan yang sama.

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + FakeBot + `asyncio.gather`, scratchpad, tidak masuk repo): dijalankan untuk **3 pemain DAN 8 pemain** (batas maksimum, sekalian uji keyboard 2-kolom tidak error untuk kursi lebih banyak) —
- lobby → join → ready-check → RUNNING,
- rebutan kursi bersamaan (dua pemain klik kursi yang sama via `asyncio.gather`) → tepat 1 yang berhasil (aman secara konkurensi walau mekanismenya masih first-click-wins, berkat lock per-session yang sudah ada di engine),
- callback dari ronde 1 ditolak setelah ronde maju ke ronde 2 (fitur baru yang sengaja ditambahkan, dites eksplisit — beda dari `simple_game` yang tidak punya proteksi ini),
- main sampai ronde final → `FINISHED` dengan pemenang tunggal yang benar, ajakan main lagi terkirim otomatis.

Item yang SENGAJA belum ada di Tahap 1 (menyusul di tahap berikutnya): jendela kontes/bobot rebutan (Tahap 2), status `AFK` beneran dipakai + narasi lengkap (Tahap 3), skor (Tahap 4), retry edit pesan & uji Telegram sungguhan (Tahap 5). Didaftarkan tanpa syarat environment di `bootstrap.py::create_game_registry()` — beda dari `simple_game` yang sengaja disembunyikan di production.

---

## Diskusi desain: skor AFK & penutupan pesan ronde lama

Dua diskusi terpisah dengan user, hasilnya masuk ke dokumen desain/kode:

**1. Skor AFK diubah dari "hangus total" jadi "penalti parsial".** User mempertanyakan: kalau AFK bisa terjadi karena masalah jaringan (bukan sengaja tidak main), apa adil skor sesi jadi 0 total (aturan lama §19/§31)? Setelah beberapa opsi dibahas (potong 50% flat, cuma hangus partisipasi, escalating penalty — yang terakhir ternyata tidak mungkin karena AFK sudah otomatis eliminasi permanen, tidak ada "AFK kedua" dalam sesi yang sama), disepakati formula: `skor_hasil_afk=0` (dipaksa, tidak ikut tabel §27), `penalty_afk = 10 + 0,5×(hasil+ketahanan)`, `skor_sesi_afk = 0,5×skor_ketahanan`. Hasilnya: pemain AFK tetap bawa pulang separuh skor ketahanan yang sudah didapat sebelum AFK, kehilangan skor hasil sepenuhnya, tidak pernah negatif. **Dokumen desain (`game-design-kursi-kosong.md` §19, §27-28, §31, §33, §45-46) sudah diperbarui** — belum ada kode (skor baru diimplementasikan di Tahap 4).

**2. Pesan ronde lama sekarang ditutup, bukan dibiarkan.** User perhatikan: begitu ronde selesai, pesan "RONDE N DIMULAI" yang lama tetap ada dengan tombol yang kelihatan masih bisa dipencet (walau secara fungsi aman ditolak berkat validasi round dari Tahap 1). Ini gap yang belum tercatat di rencana manapun — ditemukan murni dari pertanyaan user, bukan dari studi desain sebelumnya. Setelah diskusi singkat soal pembagian peran pesan (pesan lama = snapshot data, pesan baru = narasi MC — supaya tidak dobel/spam), disepakati:
- `KursiKosongGame._close_round_message()` (baru, di `game.py`) meng-edit pesan ronde lama jadi snapshot kursi final (`texts.render_round_closed` — cuma daftar kursi, tanpa narasi) dan melepas keyboard-nya (`InlineKeyboardMarkup(inline_keyboard=[])`).
- Diberi jeda `ROUND_CLOSE_PAUSE_SECONDS = 2` detik (konstanta di `metadata.py`) sebelum pesan narasi hasil ronde (yang sudah ada sejak Tahap 1, terpisah) dikirim — supaya pemain merasakan "waktu habis"/"kursi keburu penuh" alih-alih semuanya muncul instan.
- Berlaku di SEMUA ronde termasuk ronde final (sebelum pengumuman pemenang).

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + FakeBot + pengukuran waktu nyata via `time.monotonic()`): pesan ronde lama terbukti di-edit dengan teks "RONDE N SELESAI" + daftar kursi yang benar dan `reply_markup` kosong; jeda nyata terukur ~2 detik (bukan cuma dipanggil, tapi benar-benar menunda pesan berikutnya); pesan narasi hasil ronde tetap terkirim terpisah setelah jeda; berlaku juga di ronde final. Test regresi 3 & 8 pemain (dari Tahap 1) dijalankan ulang dan tetap lolos (otomatis lebih lambat karena tambahan jeda per ronde, sesuai ekspektasi).

---

## Kursi Kosong: pacing menyeluruh setelah dicoba langsung ("kurang tegang")

Setelah dua diskusi di atas, user langsung mencoba Tahap 1 dan komplain: pesan "Selamat datang..." langsung disusul pesan ronde 1 LENGKAP dengan tombol kursi, tanpa jeda sama sekali — padahal teksnya sendiri bilang "Musik akan segera dimulai!". Diskusi berlanjut ke ide user: kirim teks ronde dulu tanpa tombol, edit belakangan untuk memunculkan tombol (dikonfirmasi Telegram/aiogram mendukung ini — sama seperti pola `edit_message_reply_markup` yang sudah dipakai untuk MELEPAS keyboard, tinggal dibalik untuk MENAMBAHKAN).

**Disepakati sebagai aturan pacing umum** (khusus pesan dalam-game, bukan pesan sistem lobi/ready-check di `GameManager`):
1. Jeda 2 detik tiap kali bot kirim >1 pesan berturutan.
2. Kursi/keyboard muncul belakangan lewat edit, dengan jeda ACAK 2-4 detik dari teks ronde (bukan flat, biar tidak gampang ditebak polanya).
3. Timer 15 detik ronde dihitung SETELAH kursi muncul, bukan dari saat teks ronde dikirim (jeda pembukaan adalah waktu "mati" di luar 15 detik itu).

**Diimplementasikan** di `app/modules/games/implementations/kursi_kosong/`:
- `metadata.py`: `ROUND_CLOSE_PAUSE_SECONDS` (dari perubahan sebelumnya) di-rename jadi `MESSAGE_PAUSE_SECONDS=2` — ternyata itu instance pertama dari aturan pacing umum #1, jadi disatukan namanya. Tambah `SEAT_REVEAL_MIN_SECONDS=2`/`SEAT_REVEAL_MAX_SECONDS=4`.
- `game.py::start()`: jeda `MESSAGE_PAUSE_SECONDS` setelah welcome, sebelum ronde 1.
- `game.py::_begin_round()`: dipecah dua tahap — kirim teks ronde TANPA `reply_markup`, jeda `random.uniform(2,4)`, baru `edit_message_reply_markup` memasang keyboard, BARU `schedule_turn_timeout` dipanggil (dipindah dari posisi lama yang langsung setelah kirim pesan).
- `game.py::_resolve_round()`: tambah jeda `MESSAGE_PAUSE_SECONDS` setelah narasi hasil ronde, sebelum lanjut ke ronde berikutnya ATAU pengumuman pemenang (satu titik jeda menutupi dua cabang sekaligus).
- Pesan "Mau main lagi?" dari `GameManager.finish_game()` (generik) sengaja TIDAK diberi jeda — itu sistem, bukan dalam-game.

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + FakeBot yang mencatat timestamp `time.monotonic()` tiap event): jeda welcome→ronde ~2 detik, jeda acak sebelum keyboard muncul dalam rentang 2-4 detik, jeda narasi→ronde berikutnya ~2 detik — semua terukur nyata (bukan cuma dipanggil). Test regresi 3 & 8 pemain (Tahap 1) dijalankan ulang, tetap lolos, otomatis lebih lambat (diharapkan, karena tambahan beberapa jeda per ronde).

**Koreksi susulan (dari IDE selection user)**: user menunjuk baris "Silakan memilih kursi sebelum..." dan menunjukkan itu janggal — kalimat itu masih muncul di pesan FASE 1 (sebelum kursi/tombol ada), padahal timer belum mulai dan tombolnya belum bisa diklik sama sekali. Dipecah jadi dua fungsi teks: `render_round_waiting()` (fase 1, "Bersiaplah...", tanpa ajakan pilih kursi) dan `render_round_ready()` (fase 2, ajakan pilih kursi + hitungan waktu). `_begin_round()` diubah dari `edit_message_reply_markup` jadi `edit_message_text` untuk langkah reveal, supaya teks DAN keyboard berubah bareng di titik yang sama. Diverifikasi lewat integration test ad-hoc + regresi 3/8 pemain, tetap lolos. Catatan tambahan: user juga menyesuaikan sendiri beberapa angka pacing di kode (`MESSAGE_PAUSE_SECONDS+1` khusus jeda welcome→ronde 1, `SEAT_REVEAL_MIN/MAX_SECONDS` dari 2-4 jadi 3-5) — nilai-nilai itu dipertahankan apa adanya, bukan dikembalikan ke angka sebelumnya.

---

## Bug engine: persona (`/p1`-`/p7`) tidak dihormati di callback dalam-game

**Ditemukan lewat testing manual user**: mencoba Kursi Kosong solo lewat `/p1`, klik kursi terasa "aneh", tapi ronde keburu habis sebelum sempat digali lebih jauh.

**Investigasi** (`app/middlewares/persona.py`, `handlers/game_callbacks.py`, `handlers/lobby_callbacks.py`, `engine/manager.py`) menemukan akar masalah: `PersonaMiddleware` cuma menukar `data["current_user"]` — tidak pernah menyentuh `callback.from_user.id` (ID Telegram MENTAH pemilik akun yang benar-benar menekan tombol). Aksi LOBBY (`handle_lobby_callback`) sudah benar (pakai `current_user.id`), tapi aksi DALAM-GAME (`handle_game_callback` → `GameManager.handle_callback` → `game.handle_callback`) **tidak pernah menerima `current_user` sama sekali** — `KursiKosongGame` (dan `simple_game`, pola identik) resolve identitas lewat `callback.from_user.id` mentah. Akibatnya: kalau akun asli admin tidak ikut join sebagai pemain sendiri (pola testing solo yang umum), klik dengan persona APA PUN selalu dianggap "tidak dalam permainan" — bug ENGINE, bukan spesifik Kursi Kosong, cuma belum pernah ketahuan karena belum ada yang tes lewat persona sebelumnya.

**Diperbaiki**: tambah `GameContext.acting_user_id: int | None` (`engine/context.py`) — identitas yang SUDAH lolos resolusi persona. Di-thread dari `handlers/game_callbacks.py` (tambah param `current_user: User`, pola identik `lobby_callbacks.py`) → `GameManager.handle_callback`/`handle_message` (param baru `acting_user_id`) → `_build_context`. `KursiKosongGame.handle_callback` diubah pakai `context.acting_user_id` langsung, helper `_resolve_user_id` (yang lama, berbasis `telegram_user_id` matching) dihapus karena jadi kode mati. `simple_game` **sengaja tidak diubah** (frozen, sama seperti bug validasi round yang juga dibiarkan) — didokumentasikan eksplisit di `game-development-guide.md` §4 supaya tidak dikira kelupaan.

**Diverifikasi lewat integration test ad-hoc**: klik dengan `callback.from_user.id` SENGAJA tidak terkait pemain manapun (mensimulasikan akun asli admin), tapi `acting_user_id` diisi ID virtual player — kursi terbukti diklaim untuk `acting_user_id`, bukan `from_user.id`. Juga dites: tanpa `acting_user_id` (default `None`), klik ditolak "tidak dalam permainan" (tidak diam-diam fallback ke `from_user.id`). Regresi penuh 3 & 8 pemain (dengan `acting_user_id` dilewatkan eksplisit di tiap klik, mencerminkan cara router produksi memanggilnya) tetap lolos. Verifikasi end-to-end lewat dispatcher aiogram sungguhan (bukan panggilan langsung ke `GameManager`) belum dilakukan — direkomendasikan coba manual lewat `/p1`.."/p7" di Telegram sungguhan.

---

## Kursi Kosong Tahap 2 — Rebutan kursi sesungguhnya (jendela kontes + bobot)

**Dibangun**: mengganti first-click-wins (Tahap 1) dengan mekanisme rebutan sesuai `game-design-kursi-kosong.md` §11-14 — klik pertama ke kursi kosong membuka jendela kontes `CONTEST_WINDOW_SECONDS=1.2` detik (`schedule_timer(session_id, f"contest:{seat}", 1.2)`, timer multi-slot dari Tahap 0), klik lain ke kursi yang sama dalam jendela itu ikut masuk sebagai kontestan (bukan diproses berantai). Saat jendela habis, pemenang dipilih `random.choices` berbobot (pengklik pertama 1,25, sisanya 1,00, §13 desain). Kalau cuma 1 kontestan (tidak ada rival), kursi langsung ditetapkan diam-diam tanpa pesan grup (§23: klik normal cukup toast). Kalau ≥2, satu pesan gabungan narasi-rebutan + pengumuman-pemenang dikirim (kalimat pembuka beda untuk 2 vs >2 kontestan, §14).

**Dua keputusan desain yang tidak eksplisit di dokumen, dikonfirmasi user sebelum implementasi**:
1. Pemain yang sedang terikat kontes kursi A dan klik kursi B (berbeda) ditolak (tetap di kontes A) — bukan pindah otomatis. Mencegah satu pemain "menyebar taruhan" ke banyak kursi sekaligus.
2. Toast "kamu berhasil mengamankan kursi" dari desain tidak bisa dikirim persis seperti itu — kontes di-resolve lewat TIMER (tidak ada callback query aktif untuk dijawab saat itu, keterbatasan API Telegram, bukan pilihan desain). Diganti: toast tetap dikirim saat KLIK ("sedang memperebutkan..."), hasil akhir cukup lewat pesan grup (kontes 2+ orang) + label kursi ter-update ("🔥 Diperebutkan" → nama pemenang). Tidak ada toast personal susulan saat resolve.

**Perubahan kode**:
- `state.py`: `state["contests"]` (dict `{seat: {"contestants": [user_id,...]}}`, index 0 = pengklik pertama). Fungsi baru murni: `user_active_contest_seat`, `join_contest` (return `(joined, is_new)`), `pop_contest`, `pick_contest_winner` (terima `rng` opsional, sama pola seperti `resolve_round`).
- `game.py::handle_callback`: klik ke kursi kosong sekarang cuma memulai/ikut kontes (`join_contest` + `schedule_timer` kalau kontes baru) — TIDAK langsung `claim_seat` seperti Tahap 1. Pengecekan `is_round_complete` dipindah ke titik resolve kontes (kursi baru benar-benar terisi setelah kontes selesai, bukan saat klik).
- `game.py::handle_timeout`: membedakan `timer_key` berakhiran `:round` (timer ronde 15 detik) vs `:contest:{seat}` — dispatch ke `_resolve_round` (dengan memaksa selesaikan dulu semua kontes yang masih pending, `cancel_timer` masing-masing supaya tidak nembak dobel) atau `_resolve_contest`.
- `game.py::_settle_contest` (baru): inti logic resolve satu kursi, dipakai baik oleh jalur normal (timer 1,2 detiknya sendiri via `_resolve_contest`) maupun jalur paksa (round timeout). Pola **"timer induk memaksa selesaikan timer anak yang masih pending sebelum lanjut"** ini generik untuk game manapun yang punya beberapa timer bersarang per ronde — dicatat juga di `game-development-guide.md` §7.
- `keyboards.py`: label kursi yang sedang dikontes (belum resolve) → `"🔥 {n} · Diperebutkan"`.

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + FakeBot + `GameManager`/`TimerRegistry` sungguhan, ditulis di scratchpad): kontes 1 orang (langsung terisi, tanpa pesan grup), kontes 2 orang (keduanya tercatat, tepat 1 pesan narasi, tepat 1 menang), kontes 4 orang (semua tercatat bukan cuma 2 pertama, narasi versi ">2 orang"), klik dobel ke kontes yang sama (tidak dobel di daftar kontestan), klik ke kursi lain saat masih terikat kontes (ditolak, tetap di kontes semula), distribusi bobot `pick_contest_winner` 4000 kali percobaan dengan `random.Random` ber-seed (pengklik pertama ~28,8% vs target 29,4%, yang lain ~23-25% vs target 23,5% — sesuai §13), kontes yang jendelanya lebih panjang dari sisa waktu ronde terbukti dipaksa selesai (bukan menggantung) saat `ROUND_TIMEOUT_SECONDS` habis, dan regresi penuh 3 pemain (2 ronde sampai `FINISHED`, tepat 1 `WINNER` + 2 `ELIMINATED`).

---

## Lobby: tombol Force Start (fitur engine generik)

**Diminta user**: tambah tombol di lobi untuk melewati sisa waktu tunggu, dengan hak klik yang sama seperti tombol ❌ Batalkan (pembuat lobi ATAU admin) — bukan siapa saja yang sudah join seperti tombol ⏱ Extend. Dikonfirmasi user: cukup melewati sisa waktu LOBI saja, langsung pindah ke fase ready-check seperti biasa (pemain tetap wajib klik ✅ Siap) — bukan langsung ke RUNNING (itu akan melewati ready-check, dianggap terlalu jauh).

**Dibangun**: `GameManager.force_start_lobby()` (baru) — validasi status `LOBBY`, validasi pemain sudah ≥ `min_players` (pakai `InsufficientPlayersError` yang SEBELUMNYA sudah didefinisikan di `app/core/exceptions.py` tapi belum pernah dipakai di mana pun), batalkan timer lobi lama, lalu reuse penuh `_begin_ready_check()` yang sudah ada (dipakai juga oleh jalur timeout normal) — tidak ada logic baru untuk transisi ke STARTING. Tombol baru di `keyboards/lobby.py` (`build_lobby_keyboard`), permission check (creator-or-admin) di handler `_handle_force_start` (`handlers/lobby_callbacks.py`), pola identik `_handle_cancel` yang sudah ada.

**Cakupan**: perubahan di engine generik (`engine/manager.py`, `keyboards/lobby.py`, `handlers/lobby_callbacks.py`), bukan spesifik Kursi Kosong — berlaku untuk semua game yang pakai lobi generik.

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + `GameManager` sungguhan + pemanggilan langsung ke `_handle_force_start` untuk menguji permission check-nya, bukan cuma `GameManager`): force start oleh pembuat lobi (sukses, status `LOBBY`→`STARTING`), force start oleh admin yang bukan pembuat (sukses), force start oleh pemain biasa yang sudah join tapi bukan pembuat/admin (ditolak dengan alert, status tetap `LOBBY`), force start saat pemain masih di bawah minimum (ditolak `InsufficientPlayersError`, status tetap `LOBBY`), dan regresi `extend_lobby` (jalur normal tetap berfungsi, tidak terpengaruh).

---

## Kursi Kosong Tahap 3 — AFK vs ELIMINATED, countdown reminder, narasi ronde final

**Dibangun**: `state.py` menambah `acted_user_ids` (reset tiap ronde) + `mark_action_taken`/`took_action`. `handle_callback` menandai aksi valid di SATU titik saja — tepat setelah lolos cek `already_seated` (yaitu pemain BELUM punya kursi ronde ini) — supaya SEMUA jenis klik sesudahnya (kursi kosong, kursi sudah terisi, atau ditolak karena masih terikat kontes kursi lain) ikut terhitung valid untuk anti-AFK, persis sesuai §10 desain, tanpa perlu menambahkan pemanggilan `mark_action_taken` di tiap cabang terpisah. `_resolve_round` memakai `took_action` pada `eliminated_user_id` untuk memilih `GamePlayerStatus.AFK` vs `GamePlayerStatus.ELIMINATED`.

**Ketahuan saat implementasi (gotcha state-saving)**: karena `mark_action_taken` memutasi `state_json` SEBELUM titik-titik `return` awal di `handle_callback` (mis. cabang "masih terikat kontes lain", cabang "kursi sudah terisi"), `_save_state`+`flush()` harus dipindah ke SEGERA setelah `mark_action_taken` (bukan cuma di jalur sukses paling akhir seperti Tahap 2) — kalau tidak, mutasi `acted_user_ids` pada klik yang berujung early-return tidak akan pernah tersimpan ke database.

**Reminder countdown 5/3 detik** (§24 desain): pakai timer multi-slot yang sama seperti kontes Tahap 2 (`schedule_timer(session_id, "countdown:5"/"countdown:3", ROUND_TIMEOUT_SECONDS-5/-3)`), dijadwalkan di `_begin_round` tepat setelah timer ronde. `handle_timeout` membedakan lewat akhiran `timer_key`. Timer countdown dibatalkan (pola yang sama seperti kontes dipaksa selesai) di titik yang sama saat timer ronde dibatalkan (ronde selesai lebih cepat dari 15 detik) — supaya tidak nyasar nembak di ronde berikutnya.

**Ronde final** (§25 desain): dideteksi dari `len(state["alive_user_ids"]) == 2` di `_begin_round`, mengganti header teks ronde ("RONDE N DIMULAI!...") jadi flourish khusus lewat helper `_round_header()` di `texts.py` (dipakai FASE 1 & FASE 2 supaya tidak duplikasi kondisi).

**Bank narasi (§43 desain)** — 4 dari 5 kategori diimplementasikan pakai `random.choice`: "Kalah perebutan" (outro `render_contest_result`), "Klik kursi terisi" (`SEAT_TAKEN_ALERTS`), "AFK" & "Eliminasi" (`render_round_result`, dipilih berdasar `is_afk`). Kategori **"Berhasil duduk" SENGAJA dilewati** — constraint yang sama seperti Tahap 2: kontes 1-kontestan resolve lewat timer, tidak ada callback aktif untuk toast personal saat itu.

**Keputusan sengaja (dari plan, dikonfirmasi tanpa perlu tanya user ulang)**: §23 desain mendaftar "klik ke kursi yang sudah lama terisi" sebagai kejadian yang seharusnya "dinarasikan" (tersirat pesan grup). Diputuskan TETAP toast pribadi (bukan pesan grup baru) — mengubah jadi pesan grup berisiko spam kalau pemain berulang kali klik kursi yang sama, bertentangan dengan semangat "jangan tiap klik" di §23 sendiri. Cukup isi toast-nya diperkaya dari bank.

**Dead code dibersihkan**: `SEAT_CLAIMED_TOAST` (texts.py) dan `available_seats()` (state.py), keduanya peninggalan Tahap 1 yang sudah tidak dipanggil sejak mekanisme kontes Tahap 2 menggantikan first-click-wins.

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + `GameManager`/`TimerRegistry` sungguhan, ditulis di scratchpad): AFK murni (2 pemain klaim kursi solo, 1 pemain tidak klik apa pun sama sekali → status `AFK`), eliminated wajar (1 solo + 2 orang kontes 1 kursi, yang kalah kontes → status `ELIMINATED`, bukan `AFK`, walau sama-sama tidak dapat kursi), reminder countdown muncul tepat 1x masing-masing di waktu yang benar (diukur `time.monotonic()` relatif terhadap saat keyboard muncul, bukan dari awal test) dengan `ROUND_TIMEOUT_SECONDS` dipatch pendek (8 detik) untuk mempercepat test, countdown TIDAK nyasar muncul kalau ronde selesai lebih cepat dari waktu itu, narasi ronde final muncul saat tersisa 2 pemain. Regresi Tahap 1 & 2 dijalankan ulang, tetap lolos setelah satu penyesuaian: skenario regresi 3-pemain lama mengasumsikan non-pemenang SELALU `ELIMINATED` — sekarang bisa `AFK` ATAU `ELIMINATED` tergantung apakah pemain itu klik sesuatu di rondenya (skenario test lama sengaja tidak selalu membuat semua pemain klik tiap ronde), jadi assertion-nya diperlonggar jadi "non-winner statusnya salah satu dari AFK/ELIMINATED" alih-alih "harus ELIMINATED".

**Bug tes ditemukan (bukan bug produksi)**: skenario-skenario integration test yang TIDAK memainkan game sampai `FINISHED` (mis. cuma mengecek status setelah 1 ronde) meninggalkan sesi RUNNING dengan timer latar belakang (ronde final baru dst) yang terus menyala, mencemari `FakeBot.log` bersama DAN lock `GameManager` yang dipakai skenario BERIKUTNYA dalam file test yang sama — menyebabkan skenario lain gagal secara flaky/tidak konsisten (bukan gagal karena kode Kursi Kosong-nya salah). Diperbaiki dengan helper test `cleanup_session()` (reach ke `manager._timers.cancel_session(session_id)`, API privat, cuma untuk test) dipanggil di akhir tiap skenario yang tidak bermain sampai selesai — ditambahkan baik ke test Tahap 3 yang baru maupun (retroaktif) ke test Tahap 2 yang lama, supaya tidak ada lagi kontaminasi antar-skenario dalam satu file test.

---

## Kursi Kosong (susulan pasca-Tahap 3): revisi aturan eliminasi & jendela keadilan waktu aksi

**Ditemukan lewat pengecekan manual user** (bukan lewat gameplay, lewat membaca ulang logic-nya): user bertanya "apakah bisa eliminasi >1 pemain sekaligus?" dan "bagaimana kalau ronde selesai kelewat cepat sebelum semua sempat klik?", plus contoh konkret nyata: babak final 2 pemain/1 kursi, pemain 1 klaim kursi hampir instan, pemain 2 yang belum sempat klik sama sekali malah dicap AFK.

**Investigasi** (dicek lewat pembacaan penuh `game-design-kursi-kosong.md` dan `kursi-kosong-implementation-plan.md`, plus derivasi matematis dari `state.py::resolve_round`): dikonfirmasi kalau eliminasi memang selalu TEPAT 1 orang per ronde sejak Tahap 1 — `resolve_round` lama secara sengaja mengisi kursi yang TIDAK PERNAH diklik siapa pun dengan pemain acak dari yang tidak beraksi, semata supaya jumlah tereliminasi selalu pas `jumlah_hidup - jumlah_kursi = 1`. User mengonfirmasi ini BUKAN keputusan desain yang disengaja — cuma efek samping formula kursi yang kebetulan dia ingat, bukan aturan "harus tepat 1" yang dia maksud. Dicek juga: topik "eliminasi >1" dan "jaminan waktu minimum sebelum ronde bisa ditutup" **sama sekali tidak dibahas** di kedua dokumen desain/rencana manapun — genuinely gap baru, bukan bug implementasi dari spek yang sudah ada.

**Keputusan (dikonfirmasi user lewat pertanyaan pilihan ganda sebelum coding)**:
1. Hapus pengisian acak kursi kosong. Kursi yang benar-benar tidak pernah diklaim tetap kosong PERMANEN untuk ronde itu. Semua pemain hidup tanpa kursi tereliminasi BERSAMAAN (bisa >1 sekaligus) — mekanisme musical-chairs yang lebih jujur (cuma yang benar-benar rebutan dapat tempat).
2. Kalau ronde selesai dalam **kurang dari 6 detik** sejak kursi/keyboard muncul (`MIN_ACTION_WINDOW_SECONDS`), pemain yang belum sempat beraksi diberi keuntungan diragukan — dicap `ELIMINATED`, BUKAN `AFK`. Konsekuensi disadari & diterima user: AFK sungguhan cuma terdeteksi akurat kalau ronde berjalan >= 6 detik; tidak ada cara teknis membedakan "memang tidak mau klik" dari "belum kebagian waktu" selain elapsed time.
3. Kasus ekstrem (tidak ada satu kursi pun diklaim di satu ronde, misal semua pemain hidup diam) → semua tereliminasi bersamaan, game berakhir. Dikonfirmasi user: MC mengumumkan **tidak ada pemenang** (narasi natural), bukan pesan error/gagal seperti jalur §39 desain.

**Diimplementasikan**:
- `state.py::resolve_round(state)` ditulis ulang total — hapus parameter `rng` dan logic shuffle-isi-acak. Return type berubah dari `(survivors, eliminated_user_id: int|None)` jadi `(survivors, eliminated_ids: list[int])`.
- `metadata.py`: `MIN_ACTION_WINDOW_SECONDS = 6`.
- `game.py::_begin_round`: catat `state["ready_at"] = utcnow().isoformat()` tepat setelah keyboard benar tampil (titik yang sama seperti penjadwalan timer ronde).
- `game.py::_resolve_round`: rombak total — loop atas SEMUA `eliminated_ids` (bukan 1 id tunggal), tentukan `is_afk` PER PEMAIN dengan tambahan syarat `fair_window_passed` (elapsed sejak `ready_at` >= `MIN_ACTION_WINDOW_SECONDS`), kumpulkan nama ke kategori `normal_names`/`afk_names` terpisah untuk narasi. Cabang baru `if not survivors:` mengirim `texts.render_no_winner()` dan `finish_game(..., GameResult(winner_user_id=None, ...))`.
- `texts.py`: `render_round_result` ganti signature jadi `(normal_names: list[str], afk_names: list[str], survivor_names: list[str])` — mendukung 0-2 baris narasi eliminasi (gabungan nama dengan koma kalau lebih dari 1 orang per kategori, template bank yang sudah ada dipakai apa adanya). `render_no_winner()` baru — nada MC natural, sengaja BUKAN gaya "🚨 PERMAINAN DIHENTIKAN" dari jalur error §39.

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + `GameManager`/`TimerRegistry` sungguhan, ditulis di scratchpad):
- **Eliminasi >1 sekaligus**: 5 pemain/4 kursi, cuma kursi 1 & 2 pernah diklik (masing-masing solo) — kursi 3 & 4 terbukti TETAP kosong sampai waktu habis (bukan diisi acak), dan tepat 3 pemain (bukan 1) tereliminasi bersamaan di ronde yang sama, sedangkan 2 pemain yang dapat kursi tetap hidup.
- **Replikasi persis bug asli user**: babak final 2 pemain/1 kursi, pemain 1 klik kursi segera setelah keyboard muncul (kontes solo resolve ~1,2 detik), pemain 2 SENGAJA tidak klik apa pun — game selesai dalam <3 detik (jauh di bawah floor 6 detik), pemain 2 terbukti berstatus `ELIMINATED`, BUKAN `AFK` seperti sebelum perbaikan.
- **AFK sungguhan tetap terdeteksi**: skenario "AFK murni" dari test Tahap 3 disesuaikan — klik SENGAJA ditunda sampai lewat `MIN_ACTION_WINDOW_SECONDS` supaya pemain yang genuinely tidak pernah klik tetap benar dicap `AFK` (bukan ikut dapat "keuntungan diragukan" karena rondenya kebetulan resolve cepat).
- **Tidak ada pemenang**: skenario di mana TIDAK SATU PUN pemain klik apa pun sepanjang ronde (dengan `ROUND_TIMEOUT_SECONDS`/`MIN_ACTION_WINDOW_SECONDS` dipatch proporsional lebih kecil untuk kecepatan test, bukan cuma salah satunya — kalau cuma salah satu dipatch, floor keadilan bisa jadi lebih besar dari durasi ronde itu sendiri dan salah mengklasifikasi SEMUA pemain jadi "diberi keuntungan diragukan", termasuk yang genuinely AFK) — game `FINISHED` dengan `winner_user_id=None`, semua pemain berstatus `AFK` (ronde berjalan penuh, jadi floor keadilan terlewati secara sah), pesan MC "tanpa pemenang" terkirim (bukan framing error/gagal).
- **Regresi**: skenario kontes Tahap 2 (1/2/multi-kontestan, bobot, klik-pindah-kursi) dan skenario Tahap 3 lain (eliminated wajar, countdown, ronde final) dijalankan ulang — tetap lolos tanpa perubahan (semua skenario itu kebetulan selalu mengisi semua kursi tiap ronde, jadi berperilaku identik di bawah aturan lama maupun baru).

---

## Kursi Kosong Tahap 4 — Skor & statistik

**Dibangun**: skema & hook yang sudah disepakati sejak Tahap 0 (`game-development-guide.md` §15) akhirnya diimplementasikan. Data baru: `GamePlayer.eliminated_round` (migration `8bbf78e358b1`, dicatat bersamaan `eliminated_at` di `_resolve_round`) dan `state["initial_player_count"]` (dicatat sekali di `build_initial_state` — sengaja BUKAN jumlah pemain hidup saat ini, karena itu mengecil tiap ronde, sedangkan faktor §30 butuh jumlah pemain AWAL). Tabel `user_game_scores` + model `UserGameScore`.

**Perubahan engine generik** (`app/modules/games/engine/`): `ScoreBreakdown` dataclass baru (`score.py`), `BaseGame.calculate_scores(context, result) -> dict[user_id, ScoreBreakdown]` (default no-op, TIDAK abstrak — `simple_game` tidak perlu override). `GameManager.finish_game()` memanggil hook itu setelah `game.finish()`, lalu `game_repository.commit_scores()` (idempoten: cek dulu apakah `user_game_scores` sudah punya baris untuk `session_id` ini, skip diam-diam kalau sudah — TIDAK pakai kolom timestamp terpisah seperti `score_committed_at` yang diusulkan desain, existence-check ke tabel skor sendiri sudah cukup, lebih sederhana).

**Logic murni Kursi Kosong**: modul baru `implementations/kursi_kosong/scoring.py` (`compute_scores()`, gampang ditest tanpa DB — pola sama seperti `state.py`). Dipakai di DUA jalur oleh `game.py` supaya tidak ada logic ganda yang bisa divergen: `calculate_scores()` (dipanggil engine, untuk commit DB) dan `_send_final_results()` (dipanggil `_resolve_round` sebelum `finish_game`, untuk pesan hasil akhir §45) — keduanya membangun `PlayerOutcome` yang sama lewat helper `_build_score_outcomes()` (query SEMUA `game_players` sesi ini via `find_all_players` — fungsi repository baru, beda dari `find_active_players` yang cuma JOINED/ACTIVE).

**Revisi formula AFK ketahuan SUDAH terjadi sebelum Tahap 4 mulai**: desain §19 semula ditulis (di rencana Tahap 4, dari Tahap 0) sebagai "AFK menghanguskan skor jadi 0" — tapi saat riset ulang dokumen desain untuk implementasi, ketahuan §19 SUDAH direvisi jadi "penalti parsial" (`skor_sesi_afk = 0,5×skor_ketahanan`, BUKAN otomatis 0) di sesi sebelumnya, dengan requirement baru: pesan hasil akhir wajib menyebut angka penalti eksplisit ("AFK setelah lewat N ronde, kena penalti P poin"), bukan cuma label "AFK". Rencana Tahap 4 di `kursi-kosong-implementation-plan.md` (item 3) masih menulis versi lama saat dibaca ulang — dikoreksi sekalian saat menandai Tahap 4 selesai.

**Gap baru ditemukan & diputuskan (dikonfirmasi user via pertanyaan pilihan ganda)**: tabel skor hasil (§27: 60/40/25/10 berdasar urutan eliminasi) ditulis dengan asumsi "tepat 1 tereliminasi/ronde" — asumsi yang sudah tidak berlaku sejak susulan revisi eliminasi (entri sebelumnya di dokumen ini: >1 pemain bisa tereliminasi bersamaan). Diputuskan: ranking dihitung dari RONDE eliminasi (bukan dari jumlah pemain) — diurutkan mundur (paling akhir = tier tertinggi setelah pemenang), pemain yang tereliminasi BERSAMAAN di ronde yang sama mendapat **tier skor_hasil yang SAMA**, tidak dipisah/dirata-rata. Diimplementasikan di `scoring.py::compute_scores` — kelompokkan `eliminated_normal` (bukan AFK) berdasar `eliminated_round`, urutkan ronde descending, tier ke-N dapat skor tier ke-N dari `RESULT_SCORE_TIERS`.

**Diverifikasi lewat integration test ad-hoc** (SQLite file asli + `GameManager` sungguhan, ditulis di scratchpad): skor dasar 3 pemain (ranking 60/40/25 + partisipasi 10 + ketahanan 5/ronde, dikali faktor 1,00, dicocokkan angka pastinya lewat game yang benar-benar dimainkan sampai selesai — bukan cuma unit test murni), skor AFK dengan penalti (dicocokkan PERSIS dengan dua contoh numerik di desain §19: AFK ronde 1 → final 0, AFK setelah lewat 4 ronde → skor sesi 10 sebelum faktor), skor untuk eliminasi seri (5 pemain, cuma 2 kursi diklik, 3 pemain tereliminasi bersamaan → `result_score` ketiganya identik), commit idempoten (panggil `commit_scores` kedua kali untuk `session_id` yang sudah FINISHED → `False`, jumlah baris di `user_game_scores` tidak bertambah), faktor jumlah pemain (unit test murni `player_count_factor` untuk 3-8 pemain), format tampilan (pesan mengandung medali 🥇 dan kata "penalti"/"ronde" untuk baris AFK). Regresi Tahap 2, Tahap 3, susulan revisi eliminasi, dan Force Start dijalankan ulang — semua tetap lolos tanpa penyesuaian apa pun (murni penambahan data & pesan di titik akhir game, tidak mengubah alur gameplay yang sudah ada).

---

## Bug produksi nyata: "database is locked" + `finish_game()` bisa gagal terpanggil

**Ditemukan lewat `logs/error.log`/`logs/app.log` sungguhan** (bukan integration test) setelah Tahap 4: dua error nyata dalam sesi testing manual yang sama.

1. `sqlalchemy.exc.OperationalError: database is locked` saat `UserTrackingMiddleware` mencoba `UPDATE users SET last_seen_at=...` untuk update Telegram dari pemain LAIN — TIDAK ADA hubungan langsung dengan Kursi Kosong, korban dari koneksi LAIN yang menahan write-lock SQLite terlalu lama.
2. `aiogram.exceptions.TelegramNetworkError: Request timeout error` persis di `_send_final_results()` (kirim hasil akhir+skor) — exception ini menjalar ke atas dan membuat `_resolve_round` BERHENTI SEBELUM sempat memanggil `game_manager.finish_game(...)`.

**Akar masalah**: `GameManager.handle_callback`/timer runner membuka SATU `AsyncSession` dan cuma `commit()` SEKALI di paling akhir. Sepanjang Tahap 1-4 berkembang, `_resolve_round` jadi rangkaian panjang: beberapa `asyncio.sleep()` (pacing) + beberapa panggilan `context.bot.send_message`/`edit_message_text` (bisa lambat/timeout sungguhan di jaringan nyata, beda dari `FakeBot` di test yang selalu instan) — SEMUA di dalam SATU transaksi SQLite yang belum di-commit. Selama itu, transaksi menahan write-lock, jadi (1) koneksi LAIN yang mau menulis (mis. update user biasa) bisa kena "database is locked" begitu `busy_timeout` (5 detik) terlampaui, dan (2) kalau salah satu panggilan Telegram di tengah jalan gagal/timeout, exception menjalar ke atas dan `finish_game()` (yang mengubah status FINISHED, commit skor, DAN kirim "Mau main lagi?") tidak pernah tercapai — sesi macet RUNNING selamanya secara efektif (timer rondenya sudah terpakai, tidak ada yang memicu resolve ulang).

**Diperbaiki**:
- `kursi_kosong/game.py`: SEMUA `context.db_session.flush()` diganti `commit()` di setiap titik mutasi state — supaya write-lock dilepas SESEGERA mungkin, tidak menggantung sepanjang sleep/panggilan Telegram berikutnya. Aman karena `session_factory` dipakai dengan `expire_on_commit=False` (objek ORM tetap valid dipakai lagi sesudah commit, tidak perlu re-fetch).
- `GameManager.finish_game()` (engine, generik — jadi berlaku semua game): commit di setiap titik (set FINISHED, log event, commit skor) SEBELUM mengirim `PLAY_AGAIN_HINT` — supaya kegagalan kirim pesan itu tidak bisa lagi merusak state yang sudah semestinya permanen.
- `kursi_kosong/game.py`: semua `context.bot.send_message(...)` yang SEBELUMNYA tidak dibungkus try/except (narasi kontes, hasil ronde, tanpa-pemenang, pemenang, hasil akhir+skor) sekarang dibungkus try/except + `logger.exception(...)`, pola yang SUDAH dipakai konsisten untuk `edit_message_text`/`edit_message_reply_markup` di file yang sama sejak Tahap 1 — supaya gagal kirim SATU pesan (jaringan flaky) tidak menggagalkan `finish_game()` yang dipanggil sesudahnya. (Pesan `_begin_round`'s pertama SENGAJA dibiarkan TIDAK dibungkus — kalau itu gagal, ronde memang tidak punya pesan untuk dilekati keyboard, tidak ada yang bisa "diselamatkan"; lebih baik gagal jelas & ter-log daripada diam-diam macet.)

**Belum dikerjakan (di luar cakupan perbaikan ini, tetap bagian Tahap 5 sesuai rencana)**: retry otomatis untuk `edit_message_text` yang gagal (§36-37 desain) — perbaikan ini cuma soal BATAS TRANSAKSI & tidak-boleh-macet, bukan retry logic itu sendiri.

**Diverifikasi**: seluruh 5 file integration test ad-hoc (Tahap 2, Tahap 3, susulan eliminasi, Force Start, Tahap 4 skor) dijalankan ulang satu-per-satu setelah perubahan — semua tetap lolos tanpa penyesuaian, membuktikan commit lebih sering tidak mengubah perilaku yang sudah diuji.

---

## Perubahan format tampilan skor AFK (diminta user)

Format baris AFK di hasil akhir diringkas sesuai contoh konkret user — dari `"💤 {nama} — AFK setelah lewat N ronde, kena penalti P poin, skor akhir F poin"` jadi `"💤 {nama} (Penalti AFK {penalti} poin) - {skor akhir} poin"`. Tetap memuat angka penalti eksplisit (syarat §19 desain), cuma lebih ringkas — tidak lagi menyebut jumlah ronde yang dilewati di baris itu (datanya tetap ada di `PlayerScoreResult.rounds_passed` kalau suatu saat dibutuhkan lagi).

---

## Bug produksi nyata: game macet SELAMANYA gara-gara flood control Telegram

**Dilaporkan user via log error sungguhan** (bukan test): `aiogram.exceptions.TelegramRetryAfter: ... Flood control exceeded on method 'SendMessage' ... Retry in 10 seconds` persis di `_begin_round` — pesan pembuka ronde baru (`context.bot.send_message(waiting_text)`, dipanggil dari `_resolve_round` → `_begin_round` untuk lanjut ronde) kena limit Telegram, exception menjalar TANPA ADA yang menangkap sama sekali (satu-satunya panggilan Telegram di file ini yang memang sengaja tidak dibungkus try/except sejak perbaikan "database is locked" minggu sebelumnya — alasannya waktu itu: "kalau ini gagal, ronde memang tidak punya pesan untuk dilekati keyboard, tidak ada yang bisa diselamatkan"). Akibatnya: `state["round"]` SUDAH kepalang bertambah & ter-commit (karena perbaikan commit-per-mutasi sebelumnya), tapi tidak ada `round_message_id`, tidak ada keyboard, tidak ada timer terjadwal — game macet RUNNING selamanya. **Lebih parah**: `GameManager.cancel_game()` waktu itu CUMA menerima status LOBBY/STARTING — sama sekali tidak ada cara membatalkan sesi RUNNING yang macet, jadi grup juga tidak bisa `/game` baru (`ActiveGameExistsError`) sampai bot di-restart manual.

**Kenapa asumsi lama ("tidak ada yang bisa diselamatkan") ternyata salah**: `TelegramRetryAfter` BUKAN error acak seperti timeout jaringan biasa — Telegram secara eksplisit memberi tahu `retry_after` (detik pasti sebelum permintaan pasti akan berhasil lagi). Ini kondisi yang MEMANG bisa "diselamatkan" dengan menunggu, beda dari network error generik yang tidak ada jaminan kapan (atau apakah) akan berhasil kalau diulang.

**Diperbaiki (dua lapis, sesuai instruksi user: cek dulu, lalu perbaiki)**:
1. **Retry otomatis untuk flood control** — helper baru `_call_with_retry()` di `kursi_kosong/game.py`: tangkap khusus `TelegramRetryAfter`, tunggu `exc.retry_after + 0.5` detik, ulangi (maks 3 percobaan). SEMUA panggilan `context.bot.send_message`/`edit_message_text`/`edit_message_reply_markup` di file ini (termasuk yang sebelumnya SENGAJA dibiarkan tanpa try/except di `_begin_round`) sekarang dibungkus `_call_with_retry` — untuk yang sudah punya try/except generik, `_call_with_retry` dipanggil DI DALAM try itu (flood control ditangani lebih dulu lewat retry, exception lain tetap jatuh ke except generik seperti sebelumnya).
2. **Escape hatch manual** — `GameManager.cancel_game()` sekarang MENERIMA status `RUNNING` juga (bukan cuma LOBBY/STARTING). Untuk RUNNING, tidak ada "pesan lobi" yang relevan lagi (sudah ditutup saat game mulai) jadi kirim pesan BARU (bukan edit) memakai `render_cancelled_text` yang sudah ada (alasannya generik, tidak perlu teks baru). `/cancelgame` (`handlers/commands.py`) otomatis ikut bisa membatalkan RUNNING karena cuma memanggil `cancel_game()` — pesan error lama "Game sudah berjalan, tidak bisa dibatalkan lewat command ini" diganti "Game tidak bisa dibatalkan saat ini" (skenario itu sekarang cuma tersisa utk status transien `CREATED`, praktis tidak akan pernah terlihat). Ini murni ESCAPE HATCH manual (creator/admin) -- tidak menggantikan perbaikan #1, cuma jaring pengaman kalau ada kegagalan lain yang belum diantisipasi di masa depan.

**Untuk sesi yang SUDAH macet saat bug ini ditemukan** (sebelum fix di atas di-deploy): restart bot -- mekanisme recovery yang sudah ada (`GameManager.recover_sessions()`, dipanggil sekali saat startup) otomatis mengubah sesi RUNNING manapun jadi `ABORTED` + kirim notifikasi permintaan maaf ke grup, membebaskan grup untuk `/game` baru. Ini sudah ada SEBELUM bug ini, tidak perlu perubahan kode -- cuma perlu diingat sebagai jalan keluar darurat kalau restart adalah opsi yang tersedia.

---

## Kursi Kosong Tahap 5 (ketahanan produksi) Bagian A-C + admin monitoring

Lanjutan wajar setelah Tahap 0-4 selesai, mengikuti `kursi-kosong-implementation-plan.md` Tahap 5. Dikonfirmasi ke user dulu (lewat plan mode) sebelum coding: pesan minta maaf saat restart TETAP generic (tidak perlu narasi MC khusus Kursi Kosong), dan item admin dashboard yang tadinya ditandai opsional (`/activegames`, `/gameinfo`) DIKERJAKAN sekarang, bukan ditunda.

**Bagian A -- retry edit pesan (desain §36-37)**: gap-nya, `_call_with_retry()` yang sudah ada (dari perbaikan flood-control minggu sebelumnya) cuma menangani `TelegramRetryAfter` -- kalau `edit_message_text`/`edit_message_reply_markup` gagal karena SEBAB LAIN (network blip dkk), kode lama cuma `logger.exception(...)` lalu diam, keyboard kursi bisa basi di mata pemain SELAMANYA walau ronde sendiri tetap berjalan benar berdasar data. Diperbaiki dengan helper baru `_edit_round_message_with_fallback()`: coba edit 3x (jeda `[0, 0,5, 1,5]` detik, `_call_with_retry` tetap dipakai di tiap percobaan jadi flood control tetap tertangani seperti sebelumnya), kalau ke-3 nya tetap gagal -- kirim **pesan BARU** berisi teks+keyboard yang sama, jadikan itu `state["round_message_id"]` yang otoritatif, naikkan `state["message_version"]` (murni bookkeeping/audit, BUKAN mekanisme penegakan -- lihat paragraf berikut). Dipasang di 3 titik yang sebelumnya cuma log-lalu-diam: reveal keyboard (`_begin_round`), update kursi/kontes (`_refresh_round_message`, yang tadinya cuma `edit_message_reply_markup` markup-saja -- diganti selalu re-render teks+markup sekaligus karena teks `render_round_ready` ternyata statis per ronde, jadi aman disatukan, lihat kode untuk detail), dan reminder countdown (`_send_countdown_reminder`). `_close_round_message` (penutup ronde, keyboard dikosongkan) SENGAJA TIDAK diikutkan -- kegagalannya cuma kosmetik (keyboard lama terlihat masih aktif), validasi nomor ronde di `handle_callback` sudah menolak klik ke ronde yang sudah selesai apa pun kondisi pesannya.

Penegakan "callback dari pesan lama ditolak" (§36) diimplementasikan di `handle_callback`: bandingkan `callback.message.message_id` (kalau ada) dengan `state["round_message_id"]` saat ini, tolak (`STALE_ROUND_ALERT`, alert yang sudah ada -- tidak perlu bikin baru) kalau tidak cocok. **Keputusan desain**: dipakai perbandingan `round_message_id` LANGSUNG, bukan counter `message_version` terpisah untuk validasi -- satu pointer "pesan otoritatif saat ini" sudah cukup menegakkan "cuma 1 sumber tombol valid per ronde", lebih sederhana daripada menyimpan & membandingkan counter, hasil akhirnya sama. Perbandingannya dibuat permisif lewat `getattr` berlapis (`getattr(getattr(callback, "message", None), "message_id", None)`) supaya TIDAK crash kalau objek callback (nyata ataupun test fake) tidak punya atribut `.message` sama sekali -- gagal terbuka (permissive), bukan gagal tertutup, karena ini soal UX anti-kebingungan bukan soal keamanan.

**Bagian B -- verifikasi recovery restart**: `GameManager._abort_running_session()` (generik, sudah ada sejak awal) TIDAK diubah kodenya (sesuai keputusan user: pesan generic sudah cukup). Ditambah SATU test khusus yang membuktikan jalur ini benar-benar berlaku untuk sesi Kursi Kosong yang SUNGGUH aktif (bukan cuma lobby kosong) -- 1 kursi sudah diklaim, timer kontes/ronde aktif -- lalu simulasikan restart proses (`manager._timers.cancel_session(...)` pada instance "lama" + `GameManager` instance BARU tanpa timer/lock sama sekali, meniru proses lama yang benar-benar mati) dan panggil `recover_sessions()`. Terbukti: status jadi `ABORTED`, pesan permintaan maaf terkirim & menyebut nama game, grup bebas `/game` baru lagi.

**Admin monitoring -- `/activegames` & `/gameinfo <session_id>`**: file baru `app/modules/admin/handlers/games.py`, pola PERSIS `handlers/groups.py` yang sudah ada (`PrivateOnly()` + `IsAdmin()`, command list + command detail). Tidak perlu fungsi repository baru -- `game_repository.find_all_active()` (sudah dipakai `recover_sessions()`) sudah mengembalikan SEMUA sesi aktif lintas grup, `find_by_id`/`count_active_players` sudah cukup untuk detail. Dua presenter baru di `app/modules/admin/presenters.py`: `format_active_games_list` (tanpa paginasi -- jumlah sesi aktif bersamaan selalu kecil, beda dari daftar user/grup yang bisa ribuan baris) dan `format_game_info_detail` (menerima session_id APA PUN, termasuk yang sudah FINISHED/CANCELLED -- bukan cuma yang aktif, supaya admin bisa investigasi sesi lama juga). Didaftarkan lewat `app/modules/admin/router.py::get_router()`. `/gamesessions` dan `/admincancelgame` (dua command lain dari daftar blueprint §21.6-21.7) SENGAJA tidak dikerjakan -- di luar cakupan yang diminta di rencana Tahap 5.

**Regresi test lama -- satu penyesuaian wajib**: validasi stale-message baru di atas berarti SEMUA `FakeCallbackQuery` di file test ad-hoc lama (Tahap 2/3/4, susulan eliminasi) butuh atribut `.message.message_id` yang cocok dengan `round_message_id` state SAAT klik terjadi -- kalau tidak, klik yang seharusnya valid malah ditolak sebagai "STALE" (karena `getattr` defaultnya `None`, dan `None != round_message_id_asli`). Diperbaiki dengan menambah `_FakeMessageRef` kecil + parameter `message_id` opsional ke `FakeCallbackQuery.__init__`, dan helper `click()` di tiap file mengambil `round_message_id` terkini via `get_state()` sebelum membuat callback. TIDAK ADA perubahan logic/asersi test lain yang diperlukan -- murni penyesuaian fixture, bukti bahwa perilaku game itu sendiri tidak berubah oleh perbaikan Tahap 5 ini (cuma menambah jaring pengaman baru).

**Diverifikasi**: 3 file test ad-hoc baru (retry/fallback edit pesan -- edit gagal 1-2x lalu berhasil vs gagal 3x berturut-turut lalu fallback, klik ke pesan lama vs baru, callback tanpa `.message` tidak crash; recovery restart Kursi Kosong nyata; admin `/activegames`+`/gameinfo` lintas grup/status/argumen tidak valid) PLUS regresi penuh 6 file test lama (Tahap 2, Tahap 3, susulan eliminasi, Force Start, Tahap 4 skor, flood-control+cancel) -- semua lolos setelah penyesuaian fixture di atas. `python -c "import app.bootstrap"` tetap bersih.

**Belum dikerjakan (Bagian D, dikonfirmasi menunggu user)**: sesi manual sungguhan di Telegram pakai `/p1`.."/p7" (3 pemain + 8 pemain) -- butuh interaksi Telegram nyata, tidak bisa diotomatisasi dari sisi coding.

**Update**: Bagian D sudah dites user (3 & 8 pemain, hasilnya OK) -- Kursi Kosong Tahap 0-5 resmi TUNTAS.

---

## Panduan deployment Termux + sistem skor/leaderboard/retensi bulanan

Dua pekerjaan besar diminta sekaligus di sesi yang sama. Dikerjakan lewat plan mode (2 kali riset lewat Explore agent + 2 ronde AskUserQuestion untuk bagian yang genuinely ambigu/destruktif) sebelum ditulis kode apa pun.

### Panduan Termux

`docs/blueprint.md` §32-35 sudah punya draft prosa sejak awal project (belum pernah diimplementasikan -- `scripts/` belum ada sama sekali). Diubah jadi `docs/termux-deployment-guide.md` (panduan bernomor, ditulis untuk diikuti manual PERSIS oleh user di device Android TV Box -- tidak ada Claude di sana) + 4 script nyata di `scripts/termux/` (`install.sh`, `telegram-bot.run`, `deploy.sh`, `backup.sh`) yang ikut ter-`git pull` ke device supaya user tidak perlu ngetik ulang command panjang. Riset sebelum menulis: `requirements.txt` cuma 5 dependency (sengaja minim, penting utk Termux -- tiap dependency baru = risiko build/wheel arm64), `aiogram` menarik `pydantic-core` (Rust) dan `aiohttp`'s C-extension deps -- guide berisi peringatan+solusi (`pkg install rust binutils`) kalau `pip install` gagal build. `.env`/DB/logs semuanya sudah CWD-independent (anchored ke `BASE_DIR` via `__file__`, dikonfirmasi baca `app/core/config.py`) jadi script shell tidak perlu hati-hati soal working directory selain kebiasaan `cd` yang aman. **Belum pernah dieksekusi di device sungguhan** -- itu langkah manual user selanjutnya, tidak bisa diverifikasi otomatis.

### Sistem skor, leaderboard, & retensi data bulanan

Diminta user lewat 3 kalimat singkat yang ternyata menyembunyikan keputusan besar & DESTRUKTIF -- digali lewat AskUserQuestion sebelum coding, bukan diasumsikan:

1. **Cakupan leaderboard**: awalnya dikira "bot-wide ATAU per-grup" (pertanyaan pertama) -- user mengoreksi jawabannya sendiri: KEDUANYA. Ada skor GLOBAL per user (lintas semua grup) DAN skor per user DI SATU grup tertentu, masing-masing bisa dilihat lewat command berbeda (`/skor` menampilkan keduanya sekaligus, `/leaderboard` global, `/leaderboardgrup` per-grup). Ditambah lagi (di luar pertanyaan awal): leaderboard ANTAR-GRUP (grup vs grup, ranking berdasar total skor yang dikumpulkan grup itu) diumumkan di channel -- dikoreksi user lagi setelah draft pertama cuma menyebutnya "ringkasan" (bukan ranking sungguhan); tujuannya supaya grup terpacu ramai-ramai main biar namanya masuk peringkat atas.
2. **Mekanisme "reset"**: awalnya dikira "cukup hitung berdasar rentang tanggal, data lama tetap ada" (opsi aman tanpa hapus). User mengoreksi: **hapus fisik, tidak ada riwayat all-time sama sekali**. Ditambah lagi (bukan bagian pertanyaan awal): hapus juga `User` tidak aktif (kecuali admin) DAN `Group` tidak aktif >6 bulan -- baru ketahuan setelah dicek FK `ondelete` di seluruh model (`app/database/models/`) bahwa ini JAUH lebih destruktif dari kelihatannya: hapus 1 `Group` CASCADE menghapus SELURUH riwayat `GameSession`/`GamePlayer`/`GameEvent` yang PERNAH dimainkan di grup itu (bukan cuma skor bulan ini), hapus `User` CASCADE menghapus `GamePlayer`/`UserGameScore`/`Administrator` (baris admin DB, bukan superadmin env) miliknya. Karena tingkat destruktifnya, dikonfirmasi ULANG lewat AskUserQuestion ronde ke-2 (3 pertanyaan spesifik: ambang waktu user samakah dengan grup/6 bulan? "admin" yang dikecualikan itu superadmin env saja atau termasuk tabel `administrators` juga? user benar-benar paham konsekuensi cascade grup?) sebelum ditulis di plan -- semua dijawab "ya, sesuai rekomendasi" (6 bulan utk keduanya, DUA sumber admin dikecualikan, cascade grup diterima sepenuhnya).

**Implementasi** (modul baru `app/modules/leaderboard/`, generik lintas-game, BUKAN bagian `games/` -- sesuai intent lama yang sudah didokumentasikan di `game-development-guide.md` §15 "skor global dibagi bersama game lain"):

- **`period.py`**: perhitungan jendela bulan (berjalan vs sudah-berakhir) dalam waktu LOKAL (`settings.timezone`, pakai `zoneinfo` -- constraint baru: `zoneinfo.ZoneInfo` butuh paket `tzdata` di Windows dev, TIDAK dibutuhkan di Linux/Termux yang punya tzdata sistem, tapi ditambahkan ke `requirements.txt` supaya konsisten lintas platform & tetap aman utk Termux karena murni data Python, tanpa extension). Semua batas periode dikonversi ke naive-UTC sebelum dipakai query (konsisten dengan `utcnow()` yang dipakai di seluruh DB, lihat `app/utils/datetime.py`).
- **`leaderboard_repository.py`** (baru): agregasi skor global/per-grup, ranking antar-grup, hapus skor per rentang tanggal, cari user/grup tidak aktif (exclude admin DB lewat subquery `administrators.enabled`), hapus by-ids, marker idempotensi (`has_run`/`mark_run` -- pola exists-check sama seperti `commit_scores` Tahap 4).
- **`service.py::run_monthly_maintenance()`**: orkestrasi -- kalau channel belum diset ATAU posting ke channel gagal total, job DIBATALKAN SELURUHNYA sebelum sempat menghapus apa pun (baru dicoba lagi besok). Kegagalan posting ke SATU grup (bot di-kick dkk) TIDAK membatalkan job -- dicatat log, lanjut, skor tetap dihapus. Urutan: post channel (leaderboard global + antar-grup) → post tiap grup (leaderboard grup + mention + pesan reset) → hapus skor periode itu + tandai marker → baru MENYUSUL bersihkan user/grup tidak aktif (langkah terpisah, tidak terikat marker periode -- idempoten sendiri karena re-run cuma nemu 0 kandidat kalau sudah bersih).
- **`scheduler.py`**: loop `asyncio` polos, cek 1x/hari, TANPA dependency scheduler baru (APScheduler dkk) -- sesuai filosofi minim-dependency project. Idempoten & tahan downtime lewat marker table, bukan lewat presisi jam.
- **Presenter** (`presenters.py`): leaderboard GLOBAL & ANTAR-GRUP (versi channel) pakai nama polos TANPA mention/link (dikonfirmasi user); leaderboard per-grup (versi dikirim ke grup itu sendiri) pakai mention HTML (`<a href="tg://user?id=...">`, pola sama seperti `lobby.py`'s `_mention()`). Semua nama di-`html.escape()` sebelum diinterpolasi ke teks (bot pakai `ParseMode.HTML` default -- nama user yang kebetulan mengandung `<`/`&` bisa merusak parsing HTML kalau tidak di-escape; ini proteksi baru yang TIDAK ada di `lobby.py`'s `_mention()` lama, tapi tidak diperbaiki di sana karena di luar cakupan yang diminta). Pesan panjang (leaderboard banyak user) dipecah via `chunk_lines()` baru (`app/utils/text.py`, generik, tidak spesifik leaderboard).
- **`PLAY_AGAIN_HINT`** (`engine/lobby.py`) ditambah baris kedua yang mengarahkan ke `/skor` -- otomatis berlaku di semua jalur yang memakainya (akhir game menang, abort-restart) tanpa perlu sentuh titik lain.
- Migration baru (`0eaa57a7d5f5`): tabel kecil `monthly_maintenance_runs` (marker idempotensi). TIDAK ada kolom baru di tabel lain -- agregasi per-grup cukup lewat join `UserGameScore.session_id → GameSession.group_id`.

**Diverifikasi** lewat integration test ad-hoc (SQLite file asli, 10 skenario): chunking pesan panjang, `/skor` DM vs grup (global vs global+grup), ranking `/leaderboard` & `/leaderboardgrup` (urutan benar, mention cuma di versi grup), `run_monthly_maintenance` end-to-end sukses (post channel+grup, hapus skor total, marker tercatat, idempoten kalau dipanggil 2x), channel belum dikonfigurasi/gagal posting → job dibatalkan seluruhnya (data aman, marker tidak tercatat), 1 grup gagal post → grup lain & hapus skor tetap jalan, user/grup tidak aktif >6 bulan terhapus (admin DB & superadmin env TETAP aman), hapus grup CASCADE benar-benar menghapus `GameSession` lama, `PLAY_AGAIN_HINT` menyebut `/skor`. **Catatan metodologi baru**: skenario yang memanggil `run_monthly_maintenance` WAJIB pakai engine/DB terpisah satu sama lain -- semua memakai "bulan lalu sungguhan" (waktu nyata) sebagai periode, jadi kalau berbagi DB, skenario pertama yang jalan akan mengunci marker periode itu untuk semua skenario berikutnya (bukan bug produksi, murni isolasi test yang harus disadari saat menulisnya).

Regresi: `import app.bootstrap`/`app.main` tetap bersih, 3 file test Kursi Kosong/admin yang sudah ada dijalankan ulang (tidak tersentuh perubahan ini, cuma sanity check karena `bootstrap.py`/`lobby.py` disentuh) -- semua tetap lolos.

---

## Revisi formula skor Kursi Kosong: hapus `skor_hasil`, naikkan pengali ketahanan (fairness poin/menit lintas-game)

Dipicu pertanyaan user "apakah skor sudah fair untuk seluruh game?" setelah `game-development-guide.md` selesai dirombak (lihat entri di atas). Diskusi panjang, bertahap, TIDAK langsung eksekusi -- tiap kesimpulan dikonfirmasi ulang sebelum lanjut ke langkah berikutnya.

**Temuan awal**: formula Tahap 4 (`skor_hasil` 60/40/25/10 + `skor_partisipasi` 10 + `skor_ketahanan` 5×ronde, ×faktor pemain) TIDAK adil soal laju poin/menit. Dibuktikan pakai **data produksi nyata** dari `data/bot.db` (query langsung 20 baris `game_sessions` selesai + join `game_players` untuk jumlah pemain per sesi -- bukan asumsi/estimasi): sesi #21 (8 pemain, 7 ronde, 172 detik nyata) cuma dapat ~48 poin/menit, sedangkan sesi 3 pemain (banyak sampel, 1-2 ronde, 30-58 detik) dapat ~130-150 poin/menit -- gap ~3x. Akar masalah: `skor_hasil` & `skor_partisipasi` itu FLAT (tidak skala terhadap waktu/ronde), cuma `skor_ketahanan` yang proporsional -- game cepat dapat "bonus flat" yang sama besar dengan game lambat, dalam waktu jauh lebih singkat.

**Keputusan bertahap** (masing-masing dikonfirmasi user sebelum lanjut ke pertanyaan berikutnya):
1. Hapus `skor_hasil` sepenuhnya (bukan cuma dikurangi/dikalibrasi ulang) -- awalnya diusulkan sebagai satu dari beberapa opsi, user pilih ini secara eksplisit ("aku mau hapus skor flat juara 1 2 3 itu").
2. `skor_partisipasi` awalnya SEMPAT ikut diusulkan dihapus juga (biar makin sederhana) -- user MENOLAK & minta dipertahankan: **"kasihan buat yang eliminasi pertama, mereka sudah pakai waktunya sejak join lobi"**. Jadi pemain yang tereliminasi ronde 1 tetap dapat 10 poin (partisipasi), bukan 0 mutlak.
3. `SURVIVAL_SCORE_PER_ROUND` dinaikkan dari 5 jadi **10** (dua kali lipat) -- dikalibrasi dari data nyata (dicari titik impas aljabar: `(10+2X)/durasi_3p = 1,30×(10+7X)/durasi_8p`, hasilnya X≈9,8, dibulatkan ke 10) supaya laju 3 vs 8 pemain jadi ~36 poin/menit KEDUANYA (dari gap 3x jadi hampir setara -- sisa variasi murni dari kecepatan klik manusia yang wajar, tidak bisa dihilangkan formula apa pun).

**Pembuktian penting**: formula AFK (§19 desain, `penalty_afk = 10 + 0,5×ketahanan`, `skor_sesi_afk = 0,5×ketahanan`) **TIDAK PERLU diubah sama sekali** -- dibuktikan aljabar bahwa base `10` di `penalty_afk` itu memang persis mencoret `skor_partisipasi` (10) yang pemain normal dapat, jadi hasilnya SELALU `0,5×skor_ketahanan_afk`, terlepas dari ada/tidaknya `skor_hasil` di sisi pemain normal. Angka ABSOLUT AFK tetap ikut naik proporsional (pengali ketahanan naik dari 5 ke 10), tapi STRUKTUR formulanya tidak disentuh.

**Implementasi** (`app/modules/games/implementations/kursi_kosong/scoring.py`): hapus konstanta `RESULT_SCORE_TIERS`/`RESULT_SCORE_DEFAULT` dan seluruh blok ranking (`result_score_by_uid`, `rounds_desc` tier assignment) di `compute_scores()` -- `result_score` di `ScoreBreakdown` sekarang selalu `0` (field tetap ada, kontrak generik engine, cuma Kursi Kosong tidak mengisi lagi). `SURVIVAL_SCORE_PER_ROUND = 5` → `10`. Loop AFK TIDAK disentuh. `texts.py::render_final_results` TIDAK perlu diubah -- sudah sort by `final_score` (bukan `result_score`), medali otomatis ikut penyesuaian.

**Efek samping yang disadari & diterima** (bukan bug): "menang" sekarang cuma beda ~1 ronde ketahanan (10 poin) dari runner-up, bukan lompatan tier 20 poin seperti dulu -- trade-off sadar demi fairness poin/menit. Pemain yang tereliminasi ronde 1 (0 ronde dilewati) dapat skor SAMA dengan AFK ronde 1 (keduanya 10 poin partisipasi + 0 ketahanan = 10, atau 0 kalau benar AFK sejak awal) -- wajar, "0 ronde disurvive" ya "0 ronde disurvive" terlepas alasannya, dibedakan tetap lewat status/label di pesan, bukan lewat angka.

**Dokumentasi generik baru** (`game-development-guide.md` §15, subbagian "Kalibrasi skala biar adil lintas game" -- SENGAJA tidak menyebut Kursi Kosong sama sekali, sesuai kebijakan guide itu): pola "skor partisipasi minimal (flat) + skor progresif (skala waktu/ronde)", cara kalibrasi pakai `GameSession.started_at`/`finished_at` (kolom generik, gratis, sudah otomatis terisi -- persis yang dipakai untuk analisis data nyata di atas), dan angka acuan konkret sebagai baseline (bukan atribusi ke game manapun): partisipasi 10/0, target laju ±36 poin/menit, AFK dapat sekitar separuh laju itu.

**Dokumen lain yang disesuaikan**: `game-design-kursi-kosong.md` §26 (hapus `skor_hasil` dari rumus ikhtisar + catatan revisi), §27 (tabel tier Juara 1/2/3, DIHAPUS sepenuhnya -- penomoran lompat dari §26 ke §28), §28 (tambah alasan kenapa partisipasi dipertahankan), §29 (pengali 5→10), §30 (contoh numerik diperbarui), §19 (formula AFK disederhanakan -- hapus istilah `skor_hasil_afk` yang sudah tidak ada), §45 (contoh pesan hasil akhir, angka diperbarui ke skala baru), §46 (config `survival_score_per_round`, komentar `afk_penalty_ratio`).

**Diverifikasi**: test ad-hoc (`compute_scores()` murni, tanpa DB) untuk: skor dasar 3 pemain (menang 2 ronde → 30, eliminated ronde 1 → 10 bukan 0), skor 8 pemain menang 7 ronde → 104, AFK lewat 4 ronde → survival 40/penalty 30/final 20 (formula §19 dibuktikan tidak berubah), AFK ronde 1 → penalty 10/final 0 (sama seperti sebelumnya), eliminasi bersamaan → `final_score` SAMA (bukan lagi `result_score`, karena itu selalu 0 sekarang). Regresi test Tahap 4 penuh (commit idempoten, faktor jumlah pemain, format tampilan medali+AFK) dijalankan ulang -- semua lolos, cuma 3 asersi lama yang hardcode angka tier (60/40/80/dst) yang perlu ditulis ulang ke angka formula baru.

---

## Gating leaderboard global lewat subscribe channel + `MaintenanceGate`

Diminta lewat plan mode: `/skor` harus kasih tahu user status subscribe channel leaderboard (+ link kalau belum), dan skor cuma masuk leaderboard GLOBAL bulanan (channel) kalau usernya subscribe -- leaderboard PER-GRUP sama sekali tidak boleh kepengaruh. Dua keputusan produk digali lewat AskUserQuestion sebelum coding (lihat `docs/leaderboard-subscription-gate-implementation-plan.md` untuk detail lengkap desainnya):

1. **Scope filter**: `/leaderboard` (global, on-demand) ikut difilter juga, konsisten dengan pengumuman bulanan -- bukan cuma pengumuman channel saja. Supaya tidak ada user yang bingung "kok aku muncul di `/leaderboard` tapi nggak muncul di pengumuman channel".
2. **Mekanisme cek subscribe**: user pilih **re-verify LIVE ke Telegram tepat saat job bulanan berjalan** (bukan cuma andalkan cache lama dari `/skor`) -- supaya user yang subscribe belakangan tanpa pernah pakai `/skor` tetap tercatat benar di pengumuman bulan itu. TAPI dengan syarat tambahan: job harus tahan-gagal (1 user gagal cek jangan sampai membatalkan seluruh job), dan **selama job berjalan, user tidak boleh mulai game baru & autoreply harus dimatikan sementara** -- mencegah aktivitas yang bisa bersinggungan dengan proses rekap.

**Implementasi**:
- Kolom baru `users.is_leaderboard_channel_subscribed` (migration `db0771366137`) -- cache status subscribe, di-refresh di DUA titik: saat `/skor` dipanggil (live check 1 user), dan saat job bulanan jalan (live re-check SEMUA user berskor bulan itu, sebelum posting).
- `leaderboard_repository.py`: fungsi baru `sum_global_scores_by_user_subscribed()` (dipakai `/leaderboard`, filter cache) DAN `set_channel_subscription()`. Fungsi lama `sum_global_scores_by_user()` (TANPA filter) dipertahankan apa adanya -- dipakai job bulanan sebagai sumber mentah SEBELUM re-verifikasi live, supaya user yang cache-nya masih `False` (belum pernah `/skor`) tetap ikut dicek ulang, bukan langsung diskip.
- `service.py::run_monthly_maintenance()`: setelah ambil skor mentah, loop tiap user panggil `bot.get_chat_member()` (throttle 0.1 detik/panggilan, cegah flood limit), kumpulkan hasil sukses ke batch update cache (1 session, 1 commit) -- hasil gagal cek DIANGGAP tidak subscribe untuk siklus posting ini SAJA (cache lama TIDAK ditimpa, beda dari hasil sukses). Posting channel cuma pakai baris yang lolos re-verifikasi; posting per-grup, hapus skor (reset), dan cleanup user/grup tidak aktif **tidak diubah sama sekali** -- semua user tetap kena reset terlepas status subscribe, cuma soal siapa yang MUNCUL di pengumuman channel.
- **`app/core/maintenance.py`** (baru): `MaintenanceGate`, flag boolean in-memory sederhana (bukan `asyncio.Lock` -- cukup karena cuma dibaca/ditulis di event loop yang sama). Diset `True` oleh `run_monthly_maintenance()` persis sebelum re-verifikasi mulai, dilepas via `try/finally` (PASTI lepas walau ada exception tak terduga di tengah jalan -- dibuktikan test yang memaksa exception lewat `monkeypatch`). Dibaca oleh `handle_game_command`/`handle_game_menu_selection` (games) dan `handle_autoreply_message` (autoreply) -- keduanya menolak sementara dengan `MAINTENANCE_NOTICE` (games) atau diam total (autoreply, sesuai sifatnya yang pasif) kalau gate aktif. Cuma pembuatan lobby BARU yang diblokir -- game yang sudah berjalan boleh selesai normal (skornya otomatis lewat ke bulan berikutnya, tidak bersinggungan dengan window yang sedang direset).
- `/skor` (`handlers.py::handle_skor`): tambah `bot: Bot`, cek live subscribe (kalau channel dikonfigurasi), update cache, tempel `presenters.format_subscription_notice()` ke balasan. Kalau cek gagal (exception), cache lama dipertahankan, tidak crash.

**Diverifikasi** lewat integration test (SQLite file asli + `FakeLeaderboardBot` custom, `tests/modules/leaderboard/`, `tests/modules/games/test_maintenance_gate.py`, `tests/modules/autoreply/test_maintenance_gate.py`, total 22 test baru): filter cache repository, `/skor` 3 skenario (belum subscribe+link, sudah subscribe, gagal cek→fallback cache), `/leaderboard` cuma tampilkan subscriber, job bulanan (cuma live-subscribed yang diposting ke channel, cache di-refresh cuma utk cek yang sukses, kegagalan posting channel tetap membatalkan seluruh job seperti perilaku lama, kegagalan 1 grup tidak membatalkan job, leaderboard grup & delete tetap mencakup SEMUA user, gate selalu lepas termasuk saat dipaksa exception tak terduga), gating games & autoreply (blocked saat aktif, regresi normal saat tidak aktif). Regresi: seluruh test suite (223 test) dijalankan ulang, semua lolos.

**Belum diverifikasi manual di Telegram sungguhan** (dicatat di `project-status.md` sebagai langkah lanjutan): bot beneran jadi admin channel `GalihJK Bot Development` (`-1001126002148`), 1 user beneran subscribe & 1 belum, `/skor` masing-masing, lalu trigger job bulanan sungguhan.
