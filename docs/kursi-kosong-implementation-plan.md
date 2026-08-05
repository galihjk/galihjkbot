# Rencana Implementasi: Kursi Kosong

Rencana bertahap untuk membangun **Kursi Kosong** sebagai game pertama yang sesungguhnya (bukan game "Test"/`simple_game` yang cuma buat uji fondasi engine). Setiap tahap menghasilkan sesuatu yang bisa dites, dan tahap berikutnya boleh menunggu sampai tahap sebelumnya benar-benar jalan.

Dasar: [`game-design-kursi-kosong.md`](game-design-kursi-kosong.md) (spesifikasi desain) + [`game-development-guide.md`](game-development-guide.md) (kontrak engine, termasuk gap yang sudah diketahui dari §6-7 dan §15 di sana).

**Key & folder yang diusulkan:** `app/modules/games/implementations/kursi_kosong/`, `GameMetadata.key="kursi_kosong"`, class `KursiKosongGame`. (Desain aslinya menyebut `game_code = empty_chair` — pakai `kursi_kosong` saja supaya konsisten dengan nama Indonesia yang dipakai di semua teks bot; ganti kalau ada preferensi lain.)

---

## Tahap 0 — Pekerjaan fondasi engine (prasyarat, generik, bukan kode Kursi Kosong) — ✅ SELESAI (2026-08-04)

Tanpa ini, mekanik inti Kursi Kosong (rebutan kursi + skor) tidak bisa dibangun dengan benar. Semua di tahap ini murni perubahan `engine/`, bisa diuji terpisah tanpa Kursi Kosong sama sekali (misal pakai game "Test" yang sudah ada, atau test unit langsung).

1. **Generalisasi timer dalam-game** (lihat `game-development-guide.md` §7):
   - `GameManager.schedule_timer(session_id, name, delay_seconds)` / `cancel_timer(session_id, name)`, key jadi `turn:{session_id}:{name}` — mengizinkan beberapa timer jalan bersamaan per session (satu per kursi yang diperebutkan).
   - `schedule_turn_timeout`/`cancel_turn_timeout` yang lama bisa jadi wrapper tipis di atas API baru ini (`name="round"`) supaya `simple_game` (game Test) tidak perlu diubah.
   - Perbaiki `TimerRegistry.cancel_session()` supaya cocok dengan key berformat `turn:{id}:{name}` (bukan cuma `turn:{id}`).
   - **Test:** dua timer dengan `name` berbeda untuk session yang sama, jadwalkan bersamaan, pastikan keduanya tetap berjalan independen (tidak saling cancel), dan `cancel_session()` tetap membersihkan keduanya.

2. **Tambah `AFK` ke `GamePlayerStatus`** (`app/core/enums.py`) — tidak perlu migration (kolom `String`).

3. **Pola validasi round di callback** — bukan perubahan API, tapi keputusan konvensi yang dipakai konsisten di `KursiKosongGame.handle_callback` sejak awal (lihat contoh kode di guide §6): encode `round_number` di dalam `GameCallback.data`, tolak kalau tidak cocok `state["round"]`.

4. **Keputusan skema skor** (lihat guide §15) — putuskan bentuk tabel & hook sebelum Tahap 4 mulai, supaya tidak migration ulang:
   - Tabel baru `user_game_scores`: `id`, `user_id` (FK users.id), `game_key`, `session_id` (FK game_sessions.id), `result_score`, `participation_score`, `survival_score`, `final_score`, `committed_at`, `created_at`.
   - `BaseGame` dapat method baru (default no-op, tidak abstract — supaya game lama seperti `simple_game` tidak wajib implement):
     ```python
     async def calculate_scores(self, context: GameContext, result: GameResult) -> dict[int, int]:
         return {}  # user_id -> skor akhir; default kosong = tidak ada skor
     ```
   - `GameManager.finish_game()` panggil `calculate_scores()`, lalu commit ke `user_game_scores` **idempoten** (cek `session_id` belum pernah commit sebelumnya — analog `score_committed_at` di desain).
   - **Belum perlu dibuat sekarang** — cukup disepakati bentuknya. Migration & implementasi nyata baru di Tahap 4.

**Definition of done Tahap 0:** compile bersih, test timer multi-slot lolos, game "Test" tetap berjalan normal tanpa regresi (jalankan ulang test lama di riwayat pengembangan).

**Status implementasi:** item 1 (multi-timer) dan 2 (`AFK`) sudah dikerjakan — lihat `app/modules/games/engine/timer.py` (`cancel_session()`), `app/modules/games/engine/manager.py` (`schedule_timer`/`cancel_timer`), `app/core/enums.py` (`GamePlayerStatus.AFK`). Item 3 (konvensi validasi round) dan 4 (skema skor `user_game_scores`) sengaja **belum dikodekan** — cuma keputusan desain, baru diimplementasikan nyata masing-masing di Tahap 1 dan Tahap 4 sesuai rencana ini. Diverifikasi lewat 3 integration test ad-hoc (TimerRegistry multi-slot, GameManager.schedule_timer/cancel_timer end-to-end, regresi penuh simple_game termasuk rebutan kursi bersamaan via `asyncio.gather`) — detail di `development-history.md`.

---

## Tahap 1 — Lobby → ronde dasar (happy path, tanpa rebutan kompleks) — ✅ SELESAI (2026-08-04)

Tujuan: satu game Kursi Kosong bisa dimainkan sampai selesai, TAPI kursi masih first-click-wins sederhana (belum ada jendela rebutan 1.200ms + bobot). Ini sengaja supaya siklus lobby→ready-check→ronde→selesai (yang sudah generik dari engine) langsung terpasang dan teruji lebih dulu, sebelum menambah kerumitan rebutan.

1. `metadata.py`: `key="kursi_kosong"`, `name="Kursi Kosong"`, `min_players=3`, `max_players=8`, `lobby_timeout_seconds=60`, `ready_check_seconds=60` (fase COUNTDOWN di desain asli **sudah tercakup** oleh mekanisme ready-check generik kita — tidak perlu dibangun ulang, cukup dipetakan).
2. `state.py`: `round`, `alive_user_ids`, `seats` (mirip `simple_game/state.py`, tapi tambahkan validasi round number di setiap fungsi yang relevan).
3. `keyboards.py`: 2 kursi per baris (sesuai desain §7), `GameCallback(session_id=..., data=f"{round_number}:{chair_number}")`.
4. `texts.py`: pembukaan ronde, hasil ronde, kemenangan — pakai narasi dari `game-design-kursi-kosong.md` §14/§43 (boleh ambil beberapa dulu, tidak perlu semua varian di tahap ini).
5. `game.py`: `initialize`/`start`/`handle_callback`/`handle_timeout`/`finish` — kursi tetap first-click-wins (belum contest window), TAPI **validasi round number wajib ada dari awal** (jangan tiru bug `simple_game`).
6. Durasi ronde **15 detik** (bukan 20 seperti Test) sesuai desain §6.
7. Daftarkan di `create_game_registry()` — tanpa syarat environment (game sungguhan, tidak disembunyikan).

**Definition of done:** test integration ala yang sudah dipakai untuk `simple_game` (FakeBot + SQLite file asli + `asyncio.gather` untuk klik bersamaan) — game 3-8 pemain bisa jalan dari lobby sampai ada pemenang. Callback dari ronde lama terbukti ditolak (test khusus untuk ini, karena ini bug yang secara sadar sedang diperbaiki).

**Status implementasi:** selesai, di `app/modules/games/implementations/kursi_kosong/` (`metadata.py`, `state.py`, `keyboards.py`, `texts.py`, `game.py`), didaftarkan tanpa syarat environment di `bootstrap.py::create_game_registry()`. Keyboard menampilkan SEMUA kursi (bukan cuma yang kosong seperti `simple_game`) dengan nama pemain yang sudah duduk, di-refresh live (`edit_message_reply_markup`) tiap ada yang berhasil klaim kursi — sesuai desain §7. Validasi nomor ronde ada dari awal di `handle_callback` (format `data` pakai separator `"-"`, BUKAN `":"` — lihat gotcha baru di `game-development-guide.md` §6: `CallbackData.pack()` aiogram sendiri memakai `":"` sebagai separator field, jadi tidak bisa dipakai di dalam nilai `data`). Diverifikasi lewat integration test ad-hoc: 3 pemain DAN 8 pemain (maksimum), rebutan kursi bersamaan via `asyncio.gather` (tepat 1 menang), callback ronde lama terbukti ditolak, sampai `FINISHED` dengan pemenang benar — detail di `development-history.md`.

**Susulan kecil (ditemukan lewat pertanyaan user, bukan bagian rencana awal):** pesan ronde lama tadinya dibiarkan apa adanya setelah ronde berakhir (teks "RONDE N DIMULAI" + tombolnya tetap terlihat, walau klik ke situ sudah ditolak berkat validasi round). Sekarang `_close_round_message()` di `game.py` meng-edit pesan itu jadi snapshot kursi final (`texts.render_round_closed`) dengan keyboard kosong, diberi jeda 2 detik sebelum pesan narasi hasil ronde (terpisah, sudah ada sebelumnya) dikirim — supaya terasa "waktu habis"/"kursi keburu penuh". Diverifikasi lewat integration test ad-hoc (ukur waktu nyata + isi pesan yang di-edit).

**Susulan kedua — pacing menyeluruh (dari uji coba langsung user):** setelah Tahap 1 dicoba, user merasa alurnya terlalu instan (welcome → pesan ronde lengkap dengan tombol, tanpa jeda). Digeneralisasi jadi aturan pacing untuk SEMUA pesan dalam-game (bukan pesan sistem lobi/ready-check):
- **Jeda 2 detik** (`MESSAGE_PAUSE_SECONDS`, di `metadata.py` — nama baru untuk konstanta yang tadinya `ROUND_CLOSE_PAUSE_SECONDS`, ternyata konsep yang sama) tiap kali bot mengirim >1 pesan berturutan: welcome→teks ronde (`start()`), narasi hasil ronde→teks ronde berikutnya ATAU→pengumuman pemenang (`_resolve_round()`).
- **Kursi/keyboard tidak langsung muncul bareng teks ronde** — `_begin_round()` sekarang kirim teks ronde dulu TANPA `reply_markup`, jeda ACAK `random.uniform(SEAT_REVEAL_MIN_SECONDS, SEAT_REVEAL_MAX_SECONDS)` (2-4 detik), baru `edit_message_reply_markup` memasang keyboard.
- **Timer 15 detik (`schedule_turn_timeout`) dipindah ke SETELAH keyboard muncul** — bukan langsung setelah kirim teks ronde seperti sebelumnya, supaya jeda pembukaan tidak memotong waktu pemain memilih kursi.

Diverifikasi lewat integration test ad-hoc (urutan & timestamp nyata tiap `send_message`/`edit_message_reply_markup`) — jeda welcome→ronde, jeda acak sebelum keyboard, jeda narasi→ronde berikutnya, semuanya terukur sesuai target. Test regresi 3 & 8 pemain (Tahap 1) dijalankan ulang, tetap lolos (otomatis lebih lambat, sesuai ekspektasi).

**Susulan ketiga — teks ronde dua fase:** user mengoreksi lagi: kalimat "Silakan memilih kursi sebelum 15 detik..." tadinya sudah muncul di pesan FASE 1 (sebelum kursi ada), padahal timer belum jalan dan tombolnya belum bisa diklik — janggal. Dipecah jadi `texts.render_round_waiting()` (dikirim pertama, cuma "RONDE N DIMULAI! ... Bersiaplah, musik akan segera dimainkan...", TANPA ajakan pilih kursi/keyboard) dan `texts.render_round_ready()` (dipasang lewat `edit_message_text` BARENGAN keyboard muncul, isinya ajakan pilih kursi + hitungan waktu — karena baru di titik itu keduanya benar). `_begin_round()` di `game.py` diubah dari `edit_message_reply_markup` (cuma keyboard) jadi `edit_message_text` (teks DAN keyboard sekaligus) untuk langkah reveal. Diverifikasi lewat integration test ad-hoc + regresi 3/8 pemain, tetap lolos.

---

## Tahap 2 — Mekanisme rebutan kursi yang sesungguhnya

Ganti first-click-wins dengan mekanisme dari desain §11-13:

1. Klik pertama ke kursi kosong → kursi masuk status `CONTESTED` di `state_json`, mulai timer kontes lewat `schedule_timer(session_id, f"contest:{chair_number}", 1.2)` (hasil Tahap 0).
2. Klik lain ke kursi yang sama SELAMA jendela itu → ikut masuk daftar peserta (bukan langsung diproses).
3. Saat timer kontes berbunyi (`handle_timeout` dengan `timer_key` mengandung `contest:{chair_number}`) → pilih pemenang pakai `random.choices(peserta, weights=[1.25 jika pertama else 1.00, ...])`, tandai `SEATED`, sisanya balik `WAITING`.
4. Kursi lain yang TIDAK diklik siapa pun tidak perlu timer sama sekali (cuma yang sudah ada minimal 1 klik yang punya jendela kontes).
5. Narasi rebutan (desain §14) dikirim saat kontes dimulai/selesai — bukan tiap klik individual (desain §23: jangan spam).
6. Callback notification (toast, bukan pesan baru) untuk klik biasa: "Kamu sedang memperebutkan Kursi 4" → "Kamu berhasil mengamankan Kursi 4."

**Definition of done:** test konkurensi dengan **>2 pemain klik kursi yang sama dalam jendela 1.2 detik** (pakai `asyncio.sleep` kecil di antara klik dalam test untuk simulasi selisih waktu, bukan benar-benar bersamaan persis) — pastikan SEMUA peserta tercatat masuk kontes (bukan cuma 2 pertama), dan hasil akhir konsisten dengan bobot (jalankan berkali-kali dengan seed berbeda untuk cek distribusi kasar, bukan cuma 1 kali).

---

## Tahap 3 — AFK, eliminasi bernuansa, dan narasi lengkap

1. Bedakan `AFK` (tidak ada aksi valid SAMA SEKALI selama ronde) vs `ELIMINATED` (sudah beraksi tapi tidak kebagian kursi) — pakai status baru dari Tahap 0.
2. Klik ke kursi yang sudah lama terisi tetap dihitung "aksi valid" untuk anti-AFK (desain §10, §17) walau gagal dapat kursi.
3. Lengkapi bank narasi (§43 desain) — pisah per kategori kejadian, pilih acak saat runtime (`random.choice`).
4. Countdown 5 detik / 3 detik di dalam ronde (desain §24) — edit pesan ronde di 2 titik waktu itu saja.
5. Ronde final (2 pemain, 1 kursi) — narasi & pesan kemenangan khusus (desain §25).

**Definition of done:** test yang membedakan skenario AFK (pemain tidak klik apapun) vs eliminated (klik tapi kalah/kehabisan kursi) — pastikan status akhir keduanya berbeda di `game_players.status`.

---

## Tahap 4 — Skor & statistik

1. Migration Alembic untuk `user_game_scores` (skema sudah disepakati di Tahap 0).
2. `KursiKosongGame.calculate_scores()`: skor hasil (60/40/25/10 berdasar urutan eliminasi) + partisipasi (10 kalau ada aksi valid, 0 kalau AFK) + ketahanan (5 × jumlah ronde dilewati) × faktor jumlah pemain awal (1,00 / 1,15 / 1,30).
3. **Aturan AFK menghanguskan skor**: kalau `player.status` pernah jadi `AFK` kapan pun selama sesi → skor akhir user itu = 0 (cek ini di `calculate_scores`, bukan di engine — spesifik game ini).
4. `GameManager.finish_game()` commit skor idempoten (skip kalau `session_id` sudah pernah commit).
5. Tampilkan hasil akhir dengan skor (desain §45 — format `🥇🥈🥉` + poin).

**Definition of done:** test yang menjalankan game sampai selesai, verifikasi skor akhir tiap user sesuai formula, verifikasi commit tidak dobel kalau `finish_game` sampai terpanggil dua kali (edge case), verifikasi AFK dapat skor 0 walau sempat menang kontes sebelumnya.

---

## Tahap 5 — Ketahanan produksi & percobaan nyata

1. Retry edit pesan (desain §36-37): 3x percobaan (langsung, +500ms, +1.5s) sebelum jatuh ke kirim pesan baru.
2. Uji recovery: bot restart di tengah `ROUND_ACTIVE`-nya Kursi Kosong (level engine kita: status `RUNNING`) — sesuai kebijakan blueprint tahap awal, tetap di-ABORT (bukan resume), pastikan pesan minta maaf spesifik Kursi Kosong (bukan generic) kalau memang diinginkan beda.
3. Uji manual di Telegram pakai `/p1`.."/p7" (lihat `game-development-guide.md` §12) — minimal satu sesi penuh 3 pemain dan satu sesi 8 pemain (maksimum) untuk lihat tata letak tombol 2-kolom tidak berantakan.
4. (Opsional, boleh terpisah dari plan ini) `/activegames`, `/gameinfo <session_id>` di admin dashboard — supaya bisa dipantau lintas grup, sesuai gap yang sudah dicatat di `game-development-guide.md` §13.

**Definition of done:** satu sesi lengkap dimainkan sungguhan di Telegram (bukan cuma test otomatis) dari lobby sampai ada pemenang, layar tombol & narasi terasa sesuai nada desain ("lucu, tidak spam").

---

## Yang SENGAJA tidak masuk rencana ini (sesuai §47 desain — belum perlu versi awal)

Item, power-up, achievement, mode tertutup, level narator, spectator interaction, tim, taruhan, toko, skin kursi, sistem rank kompleks. Jangan ditambah kecuali diminta eksplisit.

## Ringkasan urutan kerja

```
Tahap 0 (engine)  →  Tahap 1 (lobby+ronde dasar)  →  Tahap 2 (rebutan+bobot)
                                                            │
                                                            ▼
                              Tahap 5 (produksi)  ←  Tahap 4 (skor)  ←  Tahap 3 (AFK+narasi)
```

Tahap 0 wajib duluan. Tahap 1→2→3 berurutan (masing-masing menambah kerumitan mekanik di atas yang sebelumnya). Tahap 4 butuh Tahap 3 selesai (skor butuh status AFK yang benar). Tahap 5 di akhir, tapi sebagian (recovery test) bisa dicicil lebih awal kalau mau.
