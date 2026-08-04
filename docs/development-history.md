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
