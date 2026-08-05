# Status Project

> Snapshot per **2026-08-05**. Dokumen ini dimutakhirkan tiap kali ada perubahan besar — kalau kamu baca ini di sesi baru, ini adalah cara TERCEPAT untuk tahu "di mana kita sekarang" tanpa baca kode. Detail teknis kenapa sesuatu dibangun begini ada di [`development-history.md`](development-history.md); detail cara nambah game ada di [`game-development-guide.md`](game-development-guide.md).

## Ringkasan super singkat

Bot Telegram jalan, bisa di-`python -m app.main` dari Windows dev. Fondasi (Fase 1-3 blueprint) **selesai** dan sudah dikeraskan (global error handler + recovery restart). Game pertama yang sesungguhnya (**Kursi Kosong**): Tahap 0 (fondasi engine) dan **Tahap 1 (lobby → ronde dasar) sudah selesai** — game bisa dimainkan sungguhan dari `/game kursi_kosong` sampai ada pemenang, TAPI kursi masih first-click-wins (belum ada jendela rebutan 1,2 detik — itu Tahap 2). Belum pernah dicoba jalan di Termux/Android TV Box sama sekali (Fase 5 blueprint nol persen).

## Yang SUDAH jalan

| Area | Status | Keterangan |
|---|---|---|
| Fondasi (config, logging, bootstrap, `/start`) | ✅ | |
| Database (SQLAlchemy async + Alembic + WAL pragma) | ✅ | 3 migration sudah jalan: users/groups/group_members, administrators, game_sessions/game_players/game_events |
| User & group tracking (middleware) | ✅ | |
| Admin: `/health`, `/users`, `/user`, `/groups`, `/group` | ✅ | Pagination via argumen command, bukan tombol |
| Admin: `/admin` dashboard dengan tombol inline | ✅ | Pengguna tercatat, aktif 24 jam, total grup, uptime |
| Testing solo: `/p0`-`/p7` (impersonasi virtual player) | ✅ | `app/modules/devtools/`, aktif di semua environment. Sekarang benar-benar dihormati juga di callback DALAM-GAME (bukan cuma lobby) lewat `GameContext.acting_user_id` — lihat baris "Engine: `acting_user_id`" di bawah |
| Game engine generik (lobby, ready-check, timer, lock) | ✅ | `app/modules/games/engine/` — lihat `game-development-guide.md` untuk kontrak lengkap |
| Alur lobby: auto-join pembuat, Extend tanpa batas, ready-check (mention+Siap+kick) | ✅ | Menggantikan total mekanisme "countdown 5s" di blueprint asli |
| Game "Test" (`simple_game`, dulu bernama "Kursi Kosong") | ✅ **frozen** | Cuma buat uji engine — kursi rebutan simpel, tanpa AFK/skor/contest-window. Disembunyikan di production |
| Engine: timer dalam-game multi-slot per session | ✅ | `GameManager.schedule_timer(session_id, name, delay)`/`cancel_timer(...)`, key `turn:{id}:{name}` — beberapa timer independen per session (prasyarat contest-window Kursi Kosong). `schedule_turn_timeout`/`cancel_turn_timeout` lama jadi wrapper (`name="round"`), `simple_game` tidak berubah. `TimerRegistry.cancel_session()` diperbaiki supaya cocok key 3-bagian |
| Status pemain `AFK` (`GamePlayerStatus`) | ✅ | Baru value enum, belum ada game yang pakai (menunggu Kursi Kosong Tahap 3) |
| Engine: `GameContext.acting_user_id` (persona-aware identity di callback dalam-game) | ✅ | Perbaikan bug nyata: `handle_game_callback` dulu tidak meneruskan `current_user` (hasil resolusi `PersonaMiddleware`) ke `GameManager`/`BaseGame`, jadi game selalu resolve identitas dari `callback.from_user.id` MENTAH — testing solo lewat `/p1`.."/p7" tidak pernah benar-benar berfungsi untuk aksi dalam-game (cuma lobby yang benar). Sekarang di-thread lewat `handle_callback`/`handle_message`/`_build_context`. `KursiKosongGame` sudah pakai; `simple_game` SENGAJA tidak diubah (frozen) |
| **Kursi Kosong Tahap 1** (`app/modules/games/implementations/kursi_kosong/`) | ✅ | 3-8 pemain, ronde 15 detik, kursi first-click-wins (belum contest window), validasi nomor ronde di callback DARI AWAL (beda dari `simple_game`), keyboard 2 kursi/baris dengan nama pemain yang sudah duduk, ter-update live tiap kali ada yang duduk. Didaftarkan tanpa syarat environment (game sungguhan). Pacing pesan dalam-game (lihat `game-development-guide.md` §16 untuk pola generiknya): teks ronde 2 fase (`render_round_waiting` "bersiaplah" → `render_round_ready` ajakan pilih kursi + keyboard, muncul bareng lewat `edit_message_text`), pesan ronde lama ditutup jadi snapshot kursi final (keyboard dilepas) sebelum narasi hasil ronde, jeda `MESSAGE_PAUSE_SECONDS`+jeda acak `SEAT_REVEAL_MIN/MAX_SECONDS` (di-tuning user ke 3-5 detik) di titik-titik transisi, timer 15 detik dihitung SETELAH kursi muncul — semua di `metadata.py`/`game.py`/`texts.py`, tidak menyentuh pesan sistem (lobi/ready-check) |
| Command `/game`, `/games`, `/gamestatus`, `/cancelgame` | ✅ | |
| Global error handler | ✅ | `app/bot/error_handler.py` — reference code ke user, notif ke superadmin, log ke `logs/error.log` |
| Recovery setelah restart | ✅ (versi tahap awal) | LOBBY/STARTING dipulihkan penuh; RUNNING di-ABORT (bukan resume mid-round — sesuai kebijakan blueprint utk versi awal) |
| Git repository | ✅ | Remote `origin` → `github.com/galihjk/galihjkbot.git`, branch `main`. Riwayat SEBELUM titik ini tidak ada di git, cuma di `development-history.md` |
| Pesan ramah (minta maaf, mention, ajakan main lagi) | ✅ | Di semua jalur cancel/finish game |

## Yang BELUM dikerjakan (urut kira-kira sesuai kebutuhan)

| Area | Status | Kenapa penting |
|---|---|---|
| **Kursi Kosong — Tahap 2 (rebutan kursi sesungguhnya)** | ❌ | Tahap 0-1 selesai (lihat tabel "SUDAH jalan"). Ganti first-click-wins dengan jendela kontes 1,2 detik + bobot 1,25/1,00 — **kandidat kerja selanjutnya yang paling jelas**, ikuti `kursi-kosong-implementation-plan.md` Tahap 2 |
| Kursi Kosong — Tahap 3 (AFK, eliminasi bernuansa, narasi lengkap) | ❌ | Menyusul setelah Tahap 2 |
| Engine: sistem skor/leaderboard lintas-game | ❌ | Prasyarat Tahap 4 Kursi Kosong (skor hasil+partisipasi+ketahanan, digabung skor global). Bentuk tabel `user_game_scores` & hook `calculate_scores()` sudah disepakati (`game-development-guide.md` §15, `kursi-kosong-implementation-plan.md` Tahap 0.4) — belum ada migration/kode, sengaja ditunda sampai Tahap 4 |
| Admin: `/activegames`, `/gamesessions`, `/gameinfo`, `/admincancelgame` | ❌ | Blueprint §21.6-21.7 — monitoring game lintas SEMUA grup dari dashboard admin (sekarang cuma bisa lihat per-grup lewat `/gamestatus` di grup itu sendiri) |
| Admin: `/errors` command, tabel `system_metrics`/`audit_logs` | ❌ | Blueprint §21.9, §16.9-16.10 — error sekarang cuma ke `logs/error.log` + Telegram, belum ada agregasi historis |
| Feature registry (§6 blueprint) | ❌ | On/off fitur per grup dari database — belum relevan selama cuma modul `games` yang aktif |
| **Deployment Termux (Fase 5 blueprint)** | ❌ 0% | Belum ada `scripts/install-termux.sh`, service runit, backup/restore script. **Belum pernah dicoba jalan di luar Windows dev sama sekali.** |
| Fase 6 (autoreply, helpdesk, game kedua, dst) | ❌ | Belum mulai, nunggu Kursi Kosong selesai dulu secara wajar |

## Langkah selanjutnya yang paling jelas

Tahap 0 dan Tahap 1 sudah selesai (diverifikasi lewat integration test nyata — lihat `development-history.md`). Lanjut ke **Tahap 2** di [`kursi-kosong-implementation-plan.md`](kursi-kosong-implementation-plan.md): ganti first-click-wins dengan mekanisme rebutan kursi sesungguhnya (jendela kontes 1,2 detik, bobot 1,25 untuk pemicu pertama, `random.choices` untuk pemenang) — pakai `GameManager.schedule_timer`/`cancel_timer` yang sudah dibangun di Tahap 0.

Alternatif kalau mau ganti arah dulu: deployment Termux, monitoring admin lintas-grup, dan lanjutan Kursi Kosong itu tiga jalur independen — bisa dikerjakan urutan berapa pun, tanya preferensi user dulu kalau mau pindah jalur.

**Kalau lanjut Tahap 2:** baca `game-development-guide.md` §7 (timer multi-slot, sudah siap dipakai) dan §16 (pacing pesan — pertahankan pola yang sudah ada di Tahap 1, jangan bikin ulang dari nol). Jendela kontes per-kursi butuh timer `schedule_timer(session_id, f"contest:{chair_number}", 1.2)` per kursi yang diperebutkan.

## Peta file cepat (kalau perlu ubah sesuatu)

| Mau ubah... | Lihat file... |
|---|---|
| Command bot baru (bukan game) | `app/modules/<nama_modul>/handlers.py` + `router.py` |
| Perilaku game yang sudah ada | `app/modules/games/implementations/<key>/game.py` |
| Alur lobby/ready-check (generik, semua game) | `app/modules/games/engine/manager.py` |
| Tabel database baru | `app/database/models/`, lalu `alembic revision --autogenerate` |
| Middleware baru (jalan di semua update) | `app/middlewares/`, daftarkan di `app/bootstrap.py::register_middlewares` |
| Konfigurasi (`.env`) | `app/core/config.py` |
