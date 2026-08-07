# Telegram Multi-Bot

Bot Telegram multifungsi (games, admin monitoring, dst) — Python + [aiogram 3](https://docs.aiogram.dev/) + SQLAlchemy 2 (async) + SQLite + Alembic. Dev di Windows, target produksi Android TV Box via Termux.

**Baru di project ini / lanjut dari sesi sebelumnya?** Baca `docs/project-status.md` dulu — itu peta paling ringkas soal apa yang sudah jalan dan apa langkah selanjutnya, tanpa perlu baca seluruh kode.

## Quick Start (Windows dev)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# isi TELEGRAM_BOT_TOKEN (dari @BotFather) dan TELEGRAM_SUPERADMIN_IDS (Telegram user ID kamu, numeric)

python -m alembic upgrade head
python -m app.main
```

Kirim `/start` ke bot di Telegram untuk memastikan jalan. `/admin` (private chat, harus superadmin) untuk dashboard.

Menjalankan test (opsional, dependency terpisah dari `requirements.txt` produksi/Termux):

```powershell
pip install -r requirements-dev.txt
pytest
```

## Struktur Proyek

```
app/
├── main.py, bootstrap.py     entrypoint & wiring dependency injection
├── core/                     config, enums, exceptions, logging
├── bot/                      factory Bot + global error handler
├── database/                 model SQLAlchemy, repository, session
├── middlewares/               database, user/group tracking, admin context, persona (testing)
├── filters/                  admin/private_only/group_only/private_input
├── services/                  health, dashboard, permission, feature (feature registry)
└── modules/
    ├── common/                /start /help
    ├── admin/                 dashboard, users, groups, health, monitoring game, /adminhelp (private chat only)
    ├── devtools/               /p0-/p7 — impersonasi admin jadi virtual player (testing solo)
    ├── games/                  engine generik (lobby/ready-check/timer/lock) + implementations/kursi_kosong (game pertama, live) + kuis_kenal (game kedua, non-production) + simple_game (game "Test", frozen)
    ├── leaderboard/            /skor, /leaderboard, /leaderboardgrup + job bulanan (umumkan+reset skor, bersihkan data tidak aktif)
    └── autoreply/              MsgCmd — rule dari Google Sheet CSV → snapshot SQLite → cache → autoreply grup (teks/media), command admin /msgcmd*

migrations/     Alembic
docs/           semua dokumentasi project (lihat di bawah)
scripts/termux/ Script deployment ke Termux (install/service/deploy/backup)
archive/        Blueprint.docx & GAME DESIGN docx asli (gitignored, sudah ditranskrip ke docs/)
```

## Dokumentasi (`docs/`)

| File | Isi | Baca kalau... |
|---|---|---|
| [`project-status.md`](docs/project-status.md) | **Mulai di sini.** Snapshot status: apa yang sudah jalan, apa yang belum, langkah selanjutnya | Baru lanjut kerja di project ini |
| [`development-history.md`](docs/development-history.md) | Kronologi keputusan & bug nyata yang ditemukan+diperbaiki (self-cancellation timer, mutasi JSON, dst) | Mau tahu KENAPA kode ditulis begini, atau sebelum ubah bagian yang sensitif |
| [`game-development-guide.md`](docs/game-development-guide.md) | Acuan lengkap cara nambah game baru di atas engine yang ada, termasuk tabel deviasi dari blueprint (§13) | Mau bikin/ubah game |
| [`game-design-kursi-kosong.md`](docs/game-design-kursi-kosong.md) | Spesifikasi desain game pertama (Kursi Kosong, Tahap 0-5 **TUNTAS**, termasuk uji manual Telegram) | Mau kerja di Kursi Kosong |
| [`kursi-kosong-implementation-plan.md`](docs/kursi-kosong-implementation-plan.md) | Rencana tahap membangun Kursi Kosong (**sudah selesai** — riwayat referensi) | Mau lihat histori keputusan tiap tahap Kursi Kosong |
| [`kuis-kenal-implementation-plan.md`](docs/kuis-kenal-implementation-plan.md) | Rencana game kedua, Kuis Kenal — kode+test otomatis selesai, belum dites manual di Telegram (Tahap 11) | Mau lanjut/uji Kuis Kenal |
| [`Desain_Pengembangan_Autoreply_MsgCmd.md`](docs/Desain_Pengembangan_Autoreply_MsgCmd.md) | Desain lengkap modul Autoreply/MsgCmd (rule Google Sheet → autoreply grup) — **sudah diimplementasikan penuh**, belum dites manual di Telegram | Mau kerja di modul autoreply |
| [`blueprint.md`](docs/blueprint.md) | Transkrip lengkap blueprint arsitektur original, plus §0 ringkasan deviasi dari kenyataan sekarang | Butuh rujukan desain awal / alasan arsitektur |
| [`termux-deployment-guide.md`](docs/termux-deployment-guide.md) | Panduan langkah-demi-langkah deploy ke Android TV Box via Termux | Mau deploy/update bot di device produksi |

## Catatan Penting

- **Git repo aktif**, remote `origin` → `github.com/galihjk/galihjkbot.git` (branch `main`). Histori keputusan/bug tetap ada di `docs/development-history.md` karena `git log` cuma mulai dari commit pertama (belum mencakup riwayat sebelum git di-setup).
- **Python 3.10** di `.venv` (bukan 3.11+) — jangan pakai `enum.StrEnum`, pakai `class X(str, Enum)`.
- Database `data/bot.db` — **jangan pindah ke shared storage** kalau nanti deploy ke Termux (WAL mode butuh filesystem lokal, lihat `blueprint.md` §28 & histori diskusi soal ini).
- Ada test suite formal (`tests/`, `pytest.ini`, `requirements-dev.txt`) — jalankan dengan `pytest`. Semua pakai SQLite file asli (bukan mock) + `FakeBot` buatan sendiri + `asyncio.gather` untuk uji konkurensi, mengikuti struktur `app/modules/` (`tests/modules/<nama_modul>/...`). Pola contohnya ada di `docs/game-development-guide.md` §12. Kursi Kosong (sebelum infra pytest ada) diverifikasi lewat script ad-hoc di scratchpad yang tidak disimpan; sejak Kuis Kenal semua verifikasi baru masuk repo sebagai test formal.
- Modul `games/implementations/simple_game` ("Test" di UI) **frozen**, jangan dikembangkan — cuma buat uji engine, disembunyikan otomatis saat `APP_ENV=production`.
- **Leaderboard bulanan bersifat DESTRUKTIF secara sengaja** (dikonfirmasi user, lihat `development-history.md`): tiap tanggal 1, `user_game_scores` bulan itu diumumkan lalu **dihapus fisik** (tidak ada riwayat all-time), DAN `User`/`Group` yang tidak aktif >6 bulan ikut dihapus (grup CASCADE menghapus seluruh riwayat game-nya). Jangan "perbaiki" ini jadi soft-delete tanpa tanya user dulu — ini keputusan produk, bukan bug.
