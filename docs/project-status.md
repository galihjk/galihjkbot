# Status Project

> Snapshot per **2026-08-04**. Dokumen ini dimutakhirkan tiap kali ada perubahan besar — kalau kamu baca ini di sesi baru, ini adalah cara TERCEPAT untuk tahu "di mana kita sekarang" tanpa baca kode. Detail teknis kenapa sesuatu dibangun begini ada di [`development-history.md`](development-history.md); detail cara nambah game ada di [`game-development-guide.md`](game-development-guide.md).

## Ringkasan super singkat

Bot Telegram jalan, bisa di-`python -m app.main` dari Windows dev. Fondasi (Fase 1-3 blueprint) **selesai** dan sudah dikeraskan (global error handler + recovery restart). Game pertama yang sesungguhnya (**Kursi Kosong**) **belum satu baris kode pun** — baru desain + rencana implementasi. Belum pernah dicoba jalan di Termux/Android TV Box sama sekali (Fase 5 blueprint nol persen).

## Yang SUDAH jalan

| Area | Status | Keterangan |
|---|---|---|
| Fondasi (config, logging, bootstrap, `/start`) | ✅ | |
| Database (SQLAlchemy async + Alembic + WAL pragma) | ✅ | 3 migration sudah jalan: users/groups/group_members, administrators, game_sessions/game_players/game_events |
| User & group tracking (middleware) | ✅ | |
| Admin: `/health`, `/users`, `/user`, `/groups`, `/group` | ✅ | Pagination via argumen command, bukan tombol |
| Admin: `/admin` dashboard dengan tombol inline | ✅ | Pengguna tercatat, aktif 24 jam, total grup, uptime |
| Testing solo: `/p0`-`/p7` (impersonasi virtual player) | ✅ | `app/modules/devtools/`, aktif di semua environment |
| Game engine generik (lobby, ready-check, timer, lock) | ✅ | `app/modules/games/engine/` — lihat `game-development-guide.md` untuk kontrak lengkap |
| Alur lobby: auto-join pembuat, Extend tanpa batas, ready-check (mention+Siap+kick) | ✅ | Menggantikan total mekanisme "countdown 5s" di blueprint asli |
| Game "Test" (`simple_game`, dulu bernama "Kursi Kosong") | ✅ **frozen** | Cuma buat uji engine — kursi rebutan simpel, tanpa AFK/skor/contest-window. Disembunyikan di production |
| Command `/game`, `/games`, `/gamestatus`, `/cancelgame` | ✅ | |
| Global error handler | ✅ | `app/bot/error_handler.py` — reference code ke user, notif ke superadmin, log ke `logs/error.log` |
| Recovery setelah restart | ✅ (versi tahap awal) | LOBBY/STARTING dipulihkan penuh; RUNNING di-ABORT (bukan resume mid-round — sesuai kebijakan blueprint utk versi awal) |
| Pesan ramah (minta maaf, mention, ajakan main lagi) | ✅ | Di semua jalur cancel/finish game |

## Yang BELUM dikerjakan (urut kira-kira sesuai kebutuhan)

| Area | Status | Kenapa penting |
|---|---|---|
| **Kursi Kosong (game pertama sesungguhnya)** | ❌ 0% kode | Desain & rencana sudah lengkap di `game-design-kursi-kosong.md` + `kursi-kosong-implementation-plan.md`. **Ini kandidat kerja selanjutnya yang paling jelas.** |
| Engine: multi-timer per session | ❌ | Prasyarat Kursi Kosong (jendela rebutan kursi 1,2 detik per kursi, bisa >1 kursi diperebutkan bersamaan) — lihat `game-development-guide.md` §7 |
| Engine: sistem skor/leaderboard lintas-game | ❌ | Prasyarat Kursi Kosong (skor hasil+partisipasi+ketahanan, digabung skor global). Rekomendasi desain ada di `game-development-guide.md` §15 — belum ada migration/kode |
| Admin: `/activegames`, `/gamesessions`, `/gameinfo`, `/admincancelgame` | ❌ | Blueprint §21.6-21.7 — monitoring game lintas SEMUA grup dari dashboard admin (sekarang cuma bisa lihat per-grup lewat `/gamestatus` di grup itu sendiri) |
| Admin: `/errors` command, tabel `system_metrics`/`audit_logs` | ❌ | Blueprint §21.9, §16.9-16.10 — error sekarang cuma ke `logs/error.log` + Telegram, belum ada agregasi historis |
| Feature registry (§6 blueprint) | ❌ | On/off fitur per grup dari database — belum relevan selama cuma modul `games` yang aktif |
| **Deployment Termux (Fase 5 blueprint)** | ❌ 0% | Belum ada `scripts/install-termux.sh`, service runit, backup/restore script. **Belum pernah dicoba jalan di luar Windows dev sama sekali.** |
| Fase 6 (autoreply, helpdesk, game kedua, dst) | ❌ | Belum mulai, nunggu Kursi Kosong selesai dulu secara wajar |
| Git repository | ❌ | Project ini **belum** `git init` — semua riwayat cuma ada di percakapan/dokumen, bukan di commit |

## Langkah selanjutnya yang paling jelas

Ikuti **Tahap 0** di [`kursi-kosong-implementation-plan.md`](kursi-kosong-implementation-plan.md) — pekerjaan fondasi engine (generalisasi timer, tambah status `AFK`, putuskan skema skor) sebelum mulai kode Kursi Kosong itu sendiri. Baca `game-development-guide.md` §6-7 dan §15 dulu untuk paham kenapa tahap ini perlu.

Alternatif kalau mau ganti arah dulu: lihat opsi lain di `project-status.md` versi sebelumnya / tanya user preferensi (deployment Termux vs monitoring admin vs Kursi Kosong) — tiga-tiganya independen, bisa dikerjakan urutan berapapun.

## Peta file cepat (kalau perlu ubah sesuatu)

| Mau ubah... | Lihat file... |
|---|---|
| Command bot baru (bukan game) | `app/modules/<nama_modul>/handlers.py` + `router.py` |
| Perilaku game yang sudah ada | `app/modules/games/implementations/<key>/game.py` |
| Alur lobby/ready-check (generik, semua game) | `app/modules/games/engine/manager.py` |
| Tabel database baru | `app/database/models/`, lalu `alembic revision --autogenerate` |
| Middleware baru (jalan di semua update) | `app/middlewares/`, daftarkan di `app/bootstrap.py::register_middlewares` |
| Konfigurasi (`.env`) | `app/core/config.py` |
