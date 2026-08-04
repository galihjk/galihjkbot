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

## Struktur Proyek

```
app/
├── main.py, bootstrap.py     entrypoint & wiring dependency injection
├── core/                     config, enums, exceptions, logging
├── bot/                      factory Bot + global error handler
├── database/                 model SQLAlchemy, repository, session
├── middlewares/               database, user/group tracking, admin context, persona (testing)
├── filters/                  admin/superadmin/private_only/group_only
├── services/                  health, dashboard, permission
└── modules/
    ├── common/                /start /help
    ├── admin/                 dashboard, users, groups, health (private chat only)
    ├── devtools/               /p0-/p7 — impersonasi admin jadi virtual player (testing solo)
    └── games/                  engine generik (lobby/ready-check/timer/lock) + implementations/simple_game (game "Test")

migrations/     Alembic
docs/           semua dokumentasi project (lihat di bawah)
archive/        Blueprint.docx & GAME DESIGN docx asli (gitignored, sudah ditranskrip ke docs/)
```

## Dokumentasi (`docs/`)

| File | Isi | Baca kalau... |
|---|---|---|
| [`project-status.md`](docs/project-status.md) | **Mulai di sini.** Snapshot status: apa yang sudah jalan, apa yang belum, langkah selanjutnya | Baru lanjut kerja di project ini |
| [`development-history.md`](docs/development-history.md) | Kronologi keputusan & bug nyata yang ditemukan+diperbaiki (self-cancellation timer, mutasi JSON, dst) | Mau tahu KENAPA kode ditulis begini, atau sebelum ubah bagian yang sensitif |
| [`game-development-guide.md`](docs/game-development-guide.md) | Acuan lengkap cara nambah game baru di atas engine yang ada | Mau bikin/ubah game |
| [`game-design-kursi-kosong.md`](docs/game-design-kursi-kosong.md) | Spesifikasi desain game pertama yang sesungguhnya (belum diimplementasikan) | Mau kerja di Kursi Kosong |
| [`kursi-kosong-implementation-plan.md`](docs/kursi-kosong-implementation-plan.md) | Rencana 6 tahap membangun Kursi Kosong | Mau mulai/lanjut implementasi Kursi Kosong |
| [`blueprint.md`](docs/blueprint.md) | Transkrip lengkap blueprint arsitektur original (39 bagian) | Butuh rujukan desain awal / alasan arsitektur |

## Catatan Penting

- **Bukan git repo** (belum di-`git init`) — riwayat perubahan cuma ada di `docs/development-history.md`, bukan di `git log`.
- **Python 3.10** di `.venv` (bukan 3.11+) — jangan pakai `enum.StrEnum`, pakai `class X(str, Enum)`.
- Database `data/bot.db` — **jangan pindah ke shared storage** kalau nanti deploy ke Termux (WAL mode butuh filesystem lokal, lihat `blueprint.md` §28 & histori diskusi soal ini).
- Belum ada test suite formal — verifikasi selama ini pakai integration test ad-hoc (SQLite file asli + `FakeBot` + `asyncio.gather` untuk uji konkurensi), ditulis di scratchpad, tidak disimpan di repo. Pola contohnya ada di `docs/game-development-guide.md` §12.
- Modul `games/implementations/simple_game` ("Test" di UI) **frozen**, jangan dikembangkan — cuma buat uji engine, disembunyikan otomatis saat `APP_ENV=production`.
