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
