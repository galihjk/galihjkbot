# Blueprint Pengembangan Bot Telegram Multifungsi

> Transkripsi lengkap dari `archive/Blueprint.docx`. Dibuat supaya folder `archive/` tidak perlu dibuka lagi — semua isi blueprint ada di sini. Dokumen ini adalah **visi arsitektur awal**, bukan cerminan status kode sungguhan — banyak bagian sudah menyimpang (sengaja) seiring pengembangan nyata. Untuk deviasi yang KHUSUS soal game engine (lobby, timer, schema `game_sessions`/`game_players`, dst), lihat tabel di [`game-development-guide.md`](game-development-guide.md) §13. Untuk deviasi di LUAR game engine (feature registry, permission, audit log, command admin, modul autoreply/leaderboard/devtools, dependency, `.env`), lihat **§0 di bawah**. Status paling akurat & terkini selalu [`project-status.md`](project-status.md), bukan dokumen ini.

Desain ini dibuat untuk kondisi berikut:

- **Server produksi**: Android TV Box + Termux
- **Komunikasi**: Telegram long polling
- **Development**: VS Code di Windows
- **Bahasa**: Python
- **Framework**: aiogram 3
- **Database**: SQLite
- **ORM**: SQLAlchemy 2
- **Migration**: Alembic
- **Arsitektur**: Modular monolith
- **Fokus tahap 1**: Satu game grup sederhana
- **Pengembangan**: Games, autoreply, helpdesk, admin tools, dan fitur lain

Aiogram mendukung asynchronous processing, router bertingkat, middleware, dependency injection, callback query, serta long polling. Long polling cocok karena tidak membutuhkan public IP atau endpoint webhook.

## 0. Status Implementasi (Ringkasan Deviasi, dimutakhirkan 2026-08-06)

Bagian ini merangkum di mana kode sungguhan menyimpang dari blueprint di bawah, DI LUAR topik game engine (yang sudah tercatat di `game-development-guide.md` §13). Baca ini dulu sebelum mempercayai detail teknis §6, §16, §19, §21, §29 di bawah secara literal.

| Area blueprint | Status sungguhan |
|---|---|
| Feature flag env `FEATURE_GAMES`/`FEATURE_ADMIN`/`FEATURE_AUTOREPLY`/dst (§6, §29) | Tidak pernah dibangun sebagai env var. `register_modules()` di `app/bootstrap.py` mendaftarkan SEMUA router modul tanpa syarat (common, admin, games, devtools, leaderboard, autoreply_admin, autoreply) — tidak ada percabangan feature-flag di titik registrasi router mana pun. |
| Feature registry §6 (tabel `features`/`group_features`) | SEKARANG SUDAH ADA di database (migration `3f8a2c9d1b47`), tapi baru dipakai modul `autoreply` lewat `app/services/feature_service.py::is_enabled()` (dicek per pesan, bukan per registrasi router). Modul `games`/`admin` TIDAK diatur lewat feature registry sama sekali — selalu aktif. Kolom sungguhan juga lebih sederhana dari blueprint: `features` = `id, feature_key, enabled_globally, created_at, updated_at` (tanpa `feature_name`, `description`, `configuration_json`); `group_features` = `id, group_id, feature_key, enabled, created_at, updated_at` (tanpa `configuration_json`). |
| Model permission admin §19.1 (matriks Viewer/Operator/Admin/Superadmin) | Matriks ini ASPIRASIONAL — sebagian besar belum sesuai kenyataan. Modul `admin` (dashboard/users/groups/health/activegames/gameinfo/adminhelp) semuanya cuma pakai `IsAdmin()` default (minimum Viewer), TIDAK ADA perbedaan hak antar-tier di modul ini. Tiering yang benar-benar berlaku baru ada di modul `autoreply` (`/msgcmd_reload`+`/msgcmd_group` butuh Operator, `/msgcmd_enable`+`/msgcmd_disable` butuh Admin). Baris "Memblokir user", "Mengubah fitur" (command generik), "Maintenance mode", "Backup manual" di tabel §19.1 — command-nya BELUM ADA sama sekali (lihat baris command di bawah). |
| `audit_logs` §16.9 | Ada (migration `3f8a2c9d1b47`), tapi kolomnya `id, actor_user_id, action, entity_type, entity_id, old_value_json, new_value_json, created_at` — TANPA `metadata_json` dan TANPA `updated_at` (immutable, sengaja). Baru dipakai aksi admin modul `autoreply` (enable/disable global, toggle grup, aktivasi snapshot) — aksi modul `games`/`admin` (mis. pembatalan game) belum diaudit ke tabel ini. |
| `system_metrics` §16.10, `command_logs` §16.8 | Belum pernah dibangun sama sekali — tidak ada migration, model, atau repository untuk keduanya. |
| Command `/errors`, `/gamesessions`, `/admincancelgame`, `/features`, `/feature <key> on\|off`, `/maintenance`, `/backup`, `/system` (§21.6-21.12) | BELUM ADA satu pun. Command monitoring yang benar-benar ada: `/admin`, `/dashboard`, `/health`, `/users`, `/user`, `/groups`, `/group`, `/activegames`, `/gameinfo`. |
| Command admin baru yang TIDAK disebut blueprint | `/adminhelp` (daftar lengkap command admin, tanda ✅/🔒 sesuai role pemanggil), `/p0`-`/p7` (persona switch untuk testing solo, modul `devtools`), dan seluruh keluarga `/msgcmd`, `/msgcmd_status`, `/msgcmd_reload`, `/msgcmd_enable`, `/msgcmd_disable`, `/msgcmd_group`, `/format_msgcmd`, `/to_msgcmd`, `/msgcmd_sync_errors` (modul `autoreply`, lihat baris di bawah). |
| Modul `autoreply` (struktur §3, flag §6/§29) | Blueprint cuma sketsa 3 file (`router.py`, `handlers.py`, `service.py`) dan menandainya nonaktif (`false`). Kenyataan: modul PENUH dengan desain terpisah `Desain_Pengembangan_Autoreply_MsgCmd.md`, SELESAI dari sisi kode+test (lihat `project-status.md`) — rule dari Google Sheet CSV, snapshot SQLite tervalidasi (strict, last-known-good), cache immutable, matcher exact/contains, grammar template custom (placeholder/mention/kondisi/tombol), 6 tipe media, 9 command admin. Diaktifkan lewat `features` (DB) + `/msgcmd_enable`, BUKAN env `FEATURE_AUTOREPLY` (env itu tidak pernah dibuat). |
| Modul `helpdesk` (struktur §3) | TIDAK ADA sama sekali — bukan cuma "fondasinya tersedia" (§37), foldernya belum pernah dibuat. |
| Modul yang TIDAK disebut blueprint tapi sekarang ADA & aktif produksi | `app/modules/leaderboard/` (`/skor`, `/leaderboard`, `/leaderboardgrup` + job pengumuman/reset bulanan otomatis), `app/modules/devtools/` (`/p0`-`/p7`). |
| Katalog game §10 (`registry.register(QuizGame())`, `WerewolfGame()`) | Game sungguhan: `KursiKosongGame` (aktif produksi), `KuisKenalGame` (disembunyikan di production, menunggu test manual Telegram), `SimpleGame` (disembunyikan di production, murni alat uji engine). Bukan `QuizGame`/`WerewolfGame`. |
| `enum.StrEnum` §7.3 | TIDAK dipakai — target Python project ini 3.10 (`StrEnum` baru ada di 3.11+). Implementasi sungguhan pakai `class GameStatus(str, Enum)`. Detail lengkap perbedaan status/event type ada di `game-development-guide.md` §13, jangan diduplikasi di sini. |
| Kolom `users`/`groups`/`administrators` §16.1-16.4 | Beberapa kolom blueprint TIDAK dibuat (belum ada konsumennya): `users.total_commands`, `total_games`, `last_private_activity_at`; `groups.bot_left_at`, `total_members_seen`, `total_games`, `settings_json`; `administrators.permissions_json`, `added_by`. (Kolom `game_sessions`/`game_players` yang tidak dibuat sudah dicatat di `game-development-guide.md` §13.) |
| Tabel yang ADA sekarang tapi TIDAK disebut blueprint sama sekali | `user_game_scores`, `monthly_maintenance_runs` (leaderboard bulanan), `settings` (key-value generik, migration `3f8a2c9d1b47`, disiapkan untuk modul mendatang — belum ada pemakainya), `autoreply_rule_sets`, `autoreply_rules`, `autoreply_sync_runs`. |
| Dependency (§29 tidak mencantumkan daftar lengkap) | `requirements.txt` sungguhan: `aiogram`, `python-dotenv`, `sqlalchemy[asyncio]`, `aiosqlite`, `alembic`, `tzdata`, `httpx` (baru, dipakai modul `autoreply` untuk fetch Google Sheet CSV). |
| `.env.example` §29 | Beda dari sampel blueprint: TIDAK ADA `LOG_RETENTION_DAYS`, `FEATURE_*`, `DEFAULT_LOBBY_TIMEOUT_SECONDS`, `DEFAULT_START_COUNTDOWN_SECONDS`, `MAINTENANCE_MODE`. ADA (tidak disebut blueprint): `TELEGRAM_LEADERBOARD_CHANNEL_ID`, `TELEGRAM_LEADERBOARD_CHANNEL_LINK`, satu blok penuh `AUTOREPLY_*` (10 variabel). `DATABASE_URL` dibiarkan kosong (default `data/bot.db` diisi kode saat runtime), bukan literal `sqlite+aiosqlite:///data/bot.db` seperti contoh blueprint. |
| Path `app/services/`, `app/filters/` §3 | Blueprint sebut `audit_service.py`, `backup_service.py`, `notification_service.py`, `monitoring_service.py` — tidak ada di `app/services/` sungguhan. Blueprint sebut `app/filters/superadmin.py`, `feature_enabled.py`, `active_game.py` — tidak ada; isi `app/filters/` sungguhan: `admin.py`, `group_only.py`, `private_only.py`, `private_input.py`. |

## 1. Sasaran Desain

Framework harus memenuhi kebutuhan berikut:

- Bot dapat mempunyai banyak jenis fitur.
- Setiap fitur berdiri sebagai modul terpisah.
- Penambahan fitur tidak mengubah fondasi bot.
- Semua game mengikuti pola umum yang sama.
- Hanya satu game aktif dalam satu grup.
- Grup berbeda boleh menjalankan game masing-masing.
- Semua game menggunakan lobby, join, timeout, start, dan finish yang sama.
- Admin dapat memonitor bot melalui command Telegram.
- Admin dapat melihat grup dan pengguna yang tercatat.
- State penting tersimpan di SQLite.
- Bot dapat pulih setelah restart.
- Pengembangan dan pengujian dilakukan di Windows.
- Deployment dilakukan melalui Git dan SSH ke Termux.

## 2. Arsitektur Tingkat Tinggi

```
┌──────────────────────────────────────────┐
│           TELEGRAM BOT API                │
└──────────────────┬───────────────────────┘
                    │ Long Polling
                    ▼
┌──────────────────────────────────────────┐
│           BOT APPLICATION                  │
│                                             │
│  ┌───────────────────────────────────┐    │
│  │  Dispatcher dan Root Router        │    │
│  └────────────────┬───────────────────┘    │
│                    │                        │
│  ┌────────────────▼───────────────────┐    │
│  │  Global Middleware                  │    │
│  │  User Tracking │ Group Tracking │    │
│  │  Auth │ DB │ Logging                │    │
│  └────────────────┬───────────────────┘    │
│                    │                        │
│  ┌────────────────▼───────────────────┐    │
│  │  Feature Modules                    │    │
│  │  Games │ Admin │ Common │           │    │
│  │  Autoreply │ Helpdesk │ Other        │    │
│  └────────────────┬───────────────────┘    │
│                    │                        │
│  ┌────────────────▼───────────────────┐    │
│  │  Application Services               │    │
│  │  GameManager │ UserService │         │    │
│  │  Monitoring │ Permissions            │    │
│  └────────────────┬───────────────────┘    │
│                    │                        │
│  ┌────────────────▼───────────────────┐    │
│  │  Repository Layer                    │    │
│  └────────────────┬───────────────────┘    │
└────────────────────┼────────────────────────┘
                      ▼
            ┌──────────────────┐
            │  SQLite Database  │
            └──────────────────┘
```

Model **modular monolith** paling sesuai. Semua fitur masih berada dalam satu aplikasi dan satu database, tetapi batas tiap modul tetap jelas. Ini ringan untuk TV box dan tetap mudah dikembangkan.

## 3. Struktur Proyek Keseluruhan

```
telegram-multibot/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── bootstrap.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── enums.py
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   ├── lifecycle.py
│   │   ├── plugin_loader.py
│   │   └── clock.py
│   │
│   ├── bot/
│   │   ├── factory.py
│   │   ├── commands.py
│   │   ├── dependencies.py
│   │   ├── error_handler.py
│   │   └── startup.py
│   │
│   ├── database/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── sqlite.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── group.py
│   │   │   ├── group_member.py
│   │   │   ├── administrator.py
│   │   │   ├── feature.py
│   │   │   ├── setting.py
│   │   │   ├── game_session.py
│   │   │   ├── game_player.py
│   │   │   ├── game_event.py
│   │   │   ├── command_log.py
│   │   │   ├── audit_log.py
│   │   │   └── system_metric.py
│   │   └── repositories/
│   │       ├── user_repository.py
│   │       ├── group_repository.py
│   │       ├── admin_repository.py
│   │       ├── feature_repository.py
│   │       ├── game_repository.py
│   │       ├── command_log_repository.py
│   │       └── metric_repository.py
│   │
│   ├── middlewares/
│   │   ├── database.py
│   │   ├── user_tracking.py
│   │   ├── group_tracking.py
│   │   ├── admin_context.py
│   │   ├── feature_gate.py
│   │   ├── rate_limit.py
│   │   ├── logging.py
│   │   └── performance.py
│   │
│   ├── filters/
│   │   ├── admin.py
│   │   ├── superadmin.py
│   │   ├── group_only.py
│   │   ├── private_only.py
│   │   ├── feature_enabled.py
│   │   └── active_game.py
│   │
│   ├── services/
│   │   ├── user_service.py
│   │   ├── group_service.py
│   │   ├── permission_service.py
│   │   ├── monitoring_service.py
│   │   ├── health_service.py
│   │   ├── feature_service.py
│   │   ├── audit_service.py
│   │   ├── backup_service.py
│   │   └── notification_service.py
│   │
│   ├── modules/
│   │   ├── common/
│   │   │   ├── router.py
│   │   │   ├── handlers.py
│   │   │   ├── keyboards.py
│   │   │   └── texts.py
│   │   │
│   │   ├── admin/
│   │   │   ├── router.py
│   │   │   ├── handlers/
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── users.py
│   │   │   │   ├── groups.py
│   │   │   │   ├── games.py
│   │   │   │   ├── health.py
│   │   │   │   ├── features.py
│   │   │   │   └── maintenance.py
│   │   │   ├── keyboards.py
│   │   │   ├── callbacks.py
│   │   │   └── presenters.py
│   │   │
│   │   ├── games/
│   │   │   ├── router.py
│   │   │   ├── engine/
│   │   │   │   ├── base_game.py
│   │   │   │   ├── manager.py
│   │   │   │   ├── registry.py
│   │   │   │   ├── lobby.py
│   │   │   │   ├── context.py
│   │   │   │   ├── timer.py
│   │   │   │   ├── lock_manager.py
│   │   │   │   ├── recovery.py
│   │   │   │   ├── metadata.py
│   │   │   │   └── result.py
│   │   │   ├── handlers/
│   │   │   │   ├── commands.py
│   │   │   │   ├── lobby_callbacks.py
│   │   │   │   ├── game_callbacks.py
│   │   │   │   └── game_messages.py
│   │   │   ├── keyboards/
│   │   │   │   ├── game_menu.py
│   │   │   │   └── lobby.py
│   │   │   └── implementations/
│   │   │       └── simple_game/
│   │   │           ├── game.py
│   │   │           ├── metadata.py
│   │   │           ├── state.py
│   │   │           ├── keyboards.py
│   │   │           └── texts.py
│   │   │
│   │   ├── autoreply/
│   │   │   ├── router.py
│   │   │   ├── handlers.py
│   │   │   └── service.py
│   │   │
│   │   └── helpdesk/
│   │       ├── router.py
│   │       ├── handlers.py
│   │       └── service.py
│   │
│   └── utils/
│       ├── telegram.py
│       ├── pagination.py
│       ├── datetime.py
│       ├── text.py
│       ├── system.py
│       └── security.py
│
├── migrations/
│   ├── env.py
│   └── versions/
│
├── scripts/
│   ├── install-termux.sh
│   ├── start.sh
│   ├── stop.sh
│   ├── restart.sh
│   ├── deploy.sh
│   ├── backup.sh
│   ├── restore.sh
│   └── healthcheck.sh
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── factories/
│
├── data/
│   ├── bot.db
│   └── backups/
│
├── logs/
├── .env.example
├── .gitignore
├── alembic.ini
├── pyproject.toml
├── requirements.txt
├── README.md
└── CHANGELOG.md
```

## 4. Pembagian Lapisan Aplikasi

### 4.1 Handler

Handler hanya menangani Telegram: membaca command, membaca callback, melakukan validasi sederhana, memanggil service, mengirim/mengedit pesan.

Handler **tidak boleh**: menjalankan SQL, menghitung aturan permainan kompleks, mengakses file `.env` secara langsung, membuat transaction sendiri, mengatur timer secara langsung.

### 4.2 Service

Service menangani proses bisnis: `GameManager`, `UserService`, `GroupService`, `MonitoringService`, `FeatureService`, `PermissionService`.

### 4.3 Repository

Repository menangani query database: `find_active_game_by_chat()`, `find_users_page()`, `count_active_users()`, `create_game_session()`, `record_player_join()`.

### 4.4 Model

Model hanya mewakili struktur database dan relasi.

### 4.5 Presenter

Presenter mengubah hasil service menjadi teks Telegram: admin dashboard, daftar user, detail user, daftar grup, game status, health report. Ini menjaga handler tetap pendek.

## 5. Sistem Modul Multifungsi

Setiap fitur mempunyai router sendiri:

```python
from aiogram import Router

router = Router(name="games")

def get_router() -> Router:
    return router
```

Plugin loader:

```python
from aiogram import Dispatcher
from app.modules.admin.router import get_router as get_admin_router
from app.modules.common.router import get_router as get_common_router
from app.modules.games.router import get_router as get_games_router

def register_modules(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(get_common_router())
    dispatcher.include_router(get_admin_router())
    dispatcher.include_router(get_games_router())
```

Modul masa depan dapat ditambahkan tanpa mengubah modul game: autoreply, helpdesk, moderation, polling, reminder, group utilities, daily challenge, leaderboard, broadcast, AI integration.

## 6. Feature Registry

Fitur disimpan di database agar dapat dinyalakan atau dimatikan.

**Tabel `features`**: `id`, `feature_key`, `feature_name`, `description`, `enabled_globally`, `configuration_json`, `created_at`, `updated_at`.

Contoh: `games` true, `admin` true, `autoreply` false, `helpdesk` false, `broadcast` false.

**Tabel `group_features`**: `id`, `group_id`, `feature_key`, `enabled`, `configuration_json`, `created_at`, `updated_at`.

Dengan demikian, suatu fitur dapat: aktif secara global, dinonaktifkan pada grup tertentu, memiliki konfigurasi khusus per grup.

## 7. Game Engine Umum

### 7.1 Aturan Utama

- Satu grup: maksimal satu game aktif.
- Grup berbeda: boleh menjalankan game bersamaan.
- Jenis game: dapat lebih dari satu.
- Lobby: komponen umum.
- Player join: melalui inline button.
- Mulai: setelah syarat minimum terpenuhi.
- Batal: jika minimum pemain tidak terpenuhi.
- State: tersimpan di SQLite.
- Timer: `asyncio` task + waktu absolut di database.

### 7.2 Lifecycle Game

```
CREATED
  │
  ▼
LOBBY
  │
  ▼
WAITING_PLAYERS ──── pemain tidak cukup ────► CANCELLED
  │
  └── pemain cukup
  ▼
STARTING
  │
  ▼
RUNNING
  │
  ▼
FINISHED
```

Status abnormal: `ABORTED`, `FAILED`, `RECOVERY_REQUIRED`.

### 7.3 Enum Status

```python
from enum import StrEnum

class GameStatus(StrEnum):
    CREATED = "created"
    LOBBY = "lobby"
    STARTING = "starting"
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    ABORTED = "aborted"
    FAILED = "failed"
```

Status aktif yang mengunci grup: `CREATED`, `LOBBY`, `STARTING`, `RUNNING`, `RECOVERY_REQUIRED`.

## 8. Kontrak Setiap Game

```python
from abc import ABC, abstractmethod
from app.modules.games.engine.context import GameContext
from app.modules.games.engine.metadata import GameMetadata
from app.modules.games.engine.result import GameResult

class BaseGame(ABC):
    metadata: GameMetadata

    async def can_start(self, context: GameContext) -> bool:
        return (
            len(context.active_players) >= self.metadata.min_players
        )

    @abstractmethod
    async def initialize(self, context: GameContext) -> None:
        """Membuat state awal game."""

    @abstractmethod
    async def start(self, context: GameContext) -> None:
        """Menjalankan game setelah lobby selesai."""

    @abstractmethod
    async def handle_message(self, context: GameContext, message) -> None:
        """Menangani pesan yang relevan dengan game."""

    @abstractmethod
    async def handle_callback(self, context: GameContext, callback) -> None:
        """Menangani tombol game."""

    @abstractmethod
    async def handle_timeout(self, context: GameContext, timer_key: str) -> None:
        """Menangani timeout ronde atau game."""

    @abstractmethod
    async def finish(self, context: GameContext, result: GameResult) -> None:
        """Menyelesaikan game."""

    async def restore(self, context: GameContext) -> None:
        """Memulihkan game setelah restart."""
        raise NotImplementedError
```

## 9. Metadata Game

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class GameMetadata:
    key: str
    name: str
    description: str
    min_players: int
    max_players: int
    lobby_timeout_seconds: int
    start_countdown_seconds: int
    supports_restore: bool = False
    enabled: bool = True
```

Contoh:

```python
SIMPLE_GAME_METADATA = GameMetadata(
    key="simple_game",
    name="Game Sederhana",
    description="Game pertama untuk menguji game engine.",
    min_players=2,
    max_players=5,
    lobby_timeout_seconds=60,
    start_countdown_seconds=5,
)
```

## 10. Game Registry

```python
class GameRegistry:
    def __init__(self) -> None:
        self._games: dict[str, BaseGame] = {}

    def register(self, game: BaseGame) -> None:
        game_key = game.metadata.key
        if game_key in self._games:
            raise ValueError(f"Game '{game_key}' sudah terdaftar")
        self._games[game_key] = game

    def get(self, game_key: str) -> BaseGame:
        try:
            return self._games[game_key]
        except KeyError as exc:
            raise GameNotFoundError(game_key) from exc

    def get_enabled(self) -> list[BaseGame]:
        return [
            game for game in self._games.values() if game.metadata.enabled
        ]
```

Nantinya: `registry.register(SimpleGame())`, `registry.register(QuizGame())`, `registry.register(WerewolfGame())`.

## 11. Game Manager

`GameManager` adalah pusat koordinasi seluruh game. Semua perubahan status harus melalui `GameManager`.

```python
class GameManager:
    async def create_lobby(self, chat_id: int, game_key: str, created_by: int): ...
    async def join_game(self, session_id: int, telegram_user_id: int): ...
    async def leave_game(self, session_id: int, telegram_user_id: int): ...
    async def begin_start_countdown(self, session_id: int): ...
    async def start_game(self, session_id: int): ...
    async def handle_message(self, chat_id: int, message): ...
    async def handle_callback(self, session_id: int, callback): ...
    async def finish_game(self, session_id: int, result): ...
    async def cancel_game(
        self, session_id: int, reason: str, cancelled_by: int | None = None
    ): ...
    async def abort_game(self, session_id: int, reason: str): ...
```

## 12. Lobby Engine

Lobby menjadi komponen umum untuk seluruh game.

```
User menjalankan /game
        │
        ▼
Bot menampilkan daftar game
        │
        ▼
User memilih game
        │
        ▼
GameManager memeriksa game aktif
        │
        ▼
Membuat session dan lobby
        │
        ▼
Pemain menekan Gabung
        │
        ▼
Pemain minimum tercapai
        │
        ▼
Countdown
        │
        ▼
Game dimulai
```

Tampilan lobby:

```
🎮 GAME SEDERHANA
Status: Menunggu pemain
Pemain: 2/5
Minimum: 2 pemain
Sisa waktu: ±45 detik

1. Galih
2. Budi

[➕ Gabung] [➖ Keluar] [❌ Batalkan]
```

Aturan lobby:

- User hanya dapat join sekali.
- Bot tidak dapat menjadi pemain.
- Pemain dapat keluar selama lobby.
- Pemain tidak dapat join setelah `STARTING`.
- Jumlah pemain tidak melewati maksimum.
- Pembuat dapat membatalkan lobby.
- Admin dapat membatalkan lobby.
- Minimum tidak terpenuhi saat timeout → batal.
- Minimum terpenuhi → countdown dan mulai.

## 13. Kebijakan Waktu Mulai

Baseline:

- Lobby dibuka selama maksimum 60 detik.
- Jika minimum pemain tercapai: countdown 5 detik dimulai; pemain lain masih boleh join selama countdown; game dimulai setelah countdown; jika pemain turun di bawah minimum, countdown dibatalkan; lobby kembali menunggu hingga timeout.

Dengan aturan ini, game tidak langsung gagal ketika seorang pemain keluar saat countdown.

## 14. Lock dan Concurrency

Beberapa user dapat menekan tombol secara bersamaan. Karena itu setiap session memerlukan lock.

```python
import asyncio

class GameLockManager:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    def get(self, session_id: int) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def remove(self, session_id: int) -> None:
        self._locks.pop(session_id, None)
```

Pemakaian:

```python
lock = lock_manager.get(session_id)
async with lock:
    await game_manager.join_game(
        session_id=session_id,
        telegram_user_id=user_id,
    )
```

Selain lock aplikasi, repository tetap harus melakukan validasi ulang di dalam transaction.

## 15. Timer Engine

Timer menggunakan `asyncio.Task`, tetapi batas waktu disimpan dalam bentuk timestamp absolut: `lobby_expires_at`, `starting_expires_at`, `turn_expires_at`, `game_expires_at`. Bukan `remaining_seconds = 60`.

Timer registry:

```python
class TimerRegistry:
    def __init__(self) -> None:
        self._tasks = {}

    def register(self, key: str, task) -> None:
        self.cancel(key)
        self._tasks[key] = task

    def cancel(self, key: str) -> None:
        task = self._tasks.pop(key, None)
        if task and not task.done():
            task.cancel()

    def cancel_session(self, session_id: int) -> None:
        prefixes = (
            f"lobby:{session_id}",
            f"starting:{session_id}",
            f"turn:{session_id}",
            f"game:{session_id}",
        )
        for key in list(self._tasks):
            if key.startswith(prefixes):
                self.cancel(key)
```

## 16. Database Inti

SQLAlchemy menyediakan ORM, transaction, dan dukungan asyncio, termasuk dialect SQLite. Alembic digunakan untuk menjaga perubahan schema database sebagai migration scripts di repository.

### 16.1 `users`

`id`, `telegram_user_id` (UNIQUE), `username`, `first_name`, `last_name`, `display_name`, `language_code`, `is_bot`, `status`, `first_seen_at`, `last_seen_at`, `last_private_activity_at`, `total_commands`, `total_games`, `created_at`, `updated_at`.

Status: `active`, `blocked`, `banned`, `inactive`.

### 16.2 `groups`

`id`, `telegram_chat_id` (UNIQUE), `title`, `username`, `chat_type`, `status`, `bot_joined_at`, `bot_left_at`, `last_activity_at`, `total_members_seen`, `total_games`, `settings_json`, `created_at`, `updated_at`.

### 16.3 `group_members`

`id`, `group_id`, `user_id`, `role`, `status`, `first_seen_at`, `last_seen_at`, `joined_at`, `left_at`, `created_at`, `updated_at`. Unique constraint: `group_id + user_id`.

### 16.4 `administrators`

`id`, `user_id`, `role`, `enabled`, `permissions_json`, `added_by`, `created_at`, `updated_at`.

Role aplikasi: `viewer`, `operator`, `admin`, `superadmin`. Ini berbeda dari administrator grup Telegram.

### 16.5 `game_sessions`

`id`, `public_id`, `group_id`, `game_key`, `status`, `created_by_user_id`, `lobby_message_id`, `min_players`, `max_players`, `lobby_expires_at`, `starting_expires_at`, `game_expires_at`, `state_json`, `result_json`, `cancellation_reason`, `error_reference`, `started_at`, `finished_at`, `cancelled_at`, `created_at`, `updated_at`.

### 16.6 `game_players`

`id`, `game_session_id`, `user_id`, `position`, `status`, `score`, `player_state_json`, `joined_at`, `left_at`, `eliminated_at`, `created_at`, `updated_at`.

Status: `joined`, `active`, `left`, `eliminated`, `winner`, `disqualified`.

### 16.7 `game_events`

`id`, `game_session_id`, `event_type`, `actor_user_id`, `payload_json`, `created_at`, `updated_at`.

Contoh event: `LOBBY_CREATED`, `PLAYER_JOINED`, `PLAYER_LEFT`, `MINIMUM_REACHED`, `COUNTDOWN_STARTED`, `COUNTDOWN_CANCELLED`, `GAME_STARTED`, `PLAYER_ACTION`, `GAME_FINISHED`, `GAME_CANCELLED`, `GAME_FAILED`.

### 16.8 `command_logs`

`id`, `user_id`, `group_id`, `command`, `module`, `success`, `duration_ms`, `error_reference`, `created_at`, `updated_at`.

Jangan menyimpan isi pesan umum ke tabel ini.

### 16.9 `audit_logs`

`id`, `actor_user_id`, `action`, `entity_type`, `entity_id`, `old_value_json`, `new_value_json`, `metadata_json`, `created_at`, `updated_at`.

### 16.10 `system_metrics`

`id`, `metric_name`, `metric_value`, `unit`, `metadata_json`, `captured_at`, `created_at`.

Contoh: `process_uptime_seconds`, `memory_usage_mb`, `disk_free_mb`, `database_size_mb`, `active_games`, `updates_processed`, `errors_last_hour`.

## 17. Tracking Pengguna

Middleware dijalankan pada setiap update yang relevan:

```
Update masuk
   │
   ▼
Baca Telegram user
   │
   ▼
Cari berdasarkan telegram_user_id
   │
   ├── Jika belum ada → buat user
   └── Jika sudah ada → perbarui nama dan last_seen
   │
   ▼
Jika update dari grup → hubungkan ke group_members
```

Data user adalah pengguna yang **pernah terlihat oleh bot**, bukan seluruh anggota Telegram dalam grup. Bot API tidak menyediakan command umum untuk mengambil daftar lengkap seluruh anggota grup. Karena itu daftar user berasal dari: user yang mengirim pesan, user yang menekan tombol, user yang menjalankan command, user yang join game, event membership yang diterima bot.

## 18. Tracking Grup

Group tracking middleware mencatat: `chat_id`, nama grup, username grup (jika ada), waktu aktivitas terakhir, saat bot pertama kali terlihat, status aktif/nonaktif, jumlah game, jumlah user yang pernah terlihat. Saat nama grup berubah, data diperbarui otomatis.

## 19. Model Hak Akses Admin

### 19.1 Role Aplikasi

| Kemampuan | Viewer | Operator | Admin | Superadmin |
|---|---|---|---|---|
| Melihat dashboard | Ya | Ya | Ya | Ya |
| Melihat pengguna | Ya | Ya | Ya | Ya |
| Melihat grup | Ya | Ya | Ya | Ya |
| Melihat game aktif | Ya | Ya | Ya | Ya |
| Membatalkan game | Tidak | Ya | Ya | Ya |
| Memblokir user | Tidak | Tidak | Ya | Ya |
| Mengubah fitur | Tidak | Tidak | Ya | Ya |
| Maintenance mode | Tidak | Tidak | Tidak | Ya |
| Backup manual | Tidak | Tidak | Tidak | Ya |
| Mengelola admin | Tidak | Tidak | Tidak | Ya |

### 19.2 Sumber Admin

Gunakan numeric Telegram user ID: `TELEGRAM_SUPERADMIN_IDS=123456789,987654321`. Admin lain disimpan di database. Username tidak digunakan sebagai identitas otorisasi karena dapat berubah.

## 20. Command Umum Pengguna

**Private chat**: `/start`, `/help`, `/about`, `/privacy`

**Grup**: `/games`, `/game`, `/howtoplay`, `/gamestatus`, `/cancelgame`, `/help`

`/howtoplay` menampilkan daftar game dengan tombol inline; klik tombol menampilkan teks cara main game tersebut (edit pesan in-place, dengan tombol "⬅️ Kembali" ke daftar).

`/game` tanpa parameter menampilkan inline menu:

```
🎮 Pilih Game
[Game Sederhana] [Game Lain — segera hadir]
```

Game yang belum aktif tidak perlu ditampilkan kepada pengguna.

## 21. Command Khusus Admin

Command admin sebaiknya dapat dijalankan di private chat dengan bot. Ini mencegah hasil monitoring memenuhi grup publik.

### 21.1 Dashboard — `/admin`, `/dashboard`

```
🛠 BOT ADMIN DASHBOARD
Status       : Online
Uptime       : 2 hari 4 jam
Versi        : 0.1.0
Environment  : Production
Pengguna tercatat : 128
Aktif 24 jam       : 19
Grup aktif          : 7
Game aktif           : 2
Game hari ini         : 14
Update diproses        : 3.482
Error 24 jam             : 1
Database                  : 3,8 MB
Storage tersedia            : 8,2 GB

[Pengguna] [Grup] [Game Aktif] [Kesehatan] [Fitur] [Refresh]
```

### 21.2 Daftar Pengguna — `/users`, `/users active`, `/users blocked`, `/users page 2`

```
👥 DAFTAR PENGGUNA
Total: 128
Halaman: 1/13

1. Galih
   ID internal: U-000128
   Telegram ID: 123456789
   Terakhir aktif: 2 menit lalu
   Game: 12
2. Budi
   ID internal: U-000127
   Terakhir aktif: 1 jam lalu
   Game: 4

[◀] [1/13] [▶]
[Filter] [Cari]
```

Gunakan pagination maksimal 10–15 pengguna per halaman.

### 21.3 Pencarian Pengguna — `/user 123456789`, `/user @username`, `/user U-000128`

```
👤 DETAIL PENGGUNA
Nama         : Galih
Username     : @galih
Telegram ID  : 123456789
Status       : Active
Pertama terlihat: 3 Agustus 2026
Terakhir aktif  : 2 menit lalu
Grup tercatat   : 3
Total game      : 12
Game menang     : 5
Command         : 34

[Riwayat Game] [Daftar Grup] [Blokir]
```

### 21.4 Daftar Grup — `/groups`, `/groups active`, `/groups inactive`

```
🏘 DAFTAR GRUP
Total grup: 7

1. Grup Development
   Chat ID: -1001234567890
   User terlihat: 32
   Game aktif: Ya
   Terakhir aktif: 1 menit lalu
2. Grup Testing
   Chat ID: -1009876543210
   User terlihat: 14
   Game aktif: Tidak
   Terakhir aktif: 3 jam lalu
```

### 21.5 Detail Grup — `/group -1001234567890`

```
🏘 DETAIL GRUP
Nama              : Grup Development
Telegram Chat ID  : -1001234567890
Status            : Active
User terlihat     : 32
Game dimainkan    : 48
Game aktif        : Game Sederhana
Fitur Games       : Aktif
Bot pertama aktif : 3 Agustus 2026
Aktivitas terakhir: 1 menit lalu

[Game Aktif] [Pengguna] [Fitur Grup]
```

### 21.6 Monitoring Game — `/activegames`, `/gamesessions`, `/gameinfo <session_id>`

```
🎮 GAME AKTIF
1. SES-000042
   Grup   : Grup Development
   Game   : Game Sederhana
   Status : Lobby
   Pemain : 2/5
   Sisa   : 31 detik
2. SES-000041
   Grup   : Grup Testing
   Game   : Game Sederhana
   Status : Running
   Pemain : 4
   Durasi : 2 menit

[Refresh]
```

### 21.7 Membatalkan Game — `/admincancelgame <session_id>`

```
Batalkan game SES-000042?
Grup: Grup Development
Status: Lobby
Pemain: 2

[Ya, Batalkan] [Kembali]
```

Pembatalan dicatat ke audit log.

### 21.8 Health Check — `/health`, `/system`

```
🟢 SYSTEM HEALTH
Bot API     : Connected
Database    : Healthy
Polling     : Running
Service     : Active
Uptime      : 2 hari 4 jam
Memory      : 142 MB
Database    : 3,8 MB
Storage bebas: 8,2 GB
Active timers: 3
Active games : 2
Update terakhir: 3 detik lalu
Backup terakhir : Hari ini, 03.00 WIB
```

### 21.9 Error Monitoring — `/errors`, `/errors today`

```
⚠️ ERROR SUMMARY
24 jam terakhir : 3
1 jam terakhir  : 0
Kritis          : 0

Terakhir:
ERR-A82F10
Module: games
Type: TelegramBadRequest
Time: 12.42 WIB
```

Tidak perlu menampilkan stack trace di Telegram.

### 21.10 Feature Management — `/features`, `/feature games on`, `/feature autoreply off`

```
🧩 FEATURES
✅ Games
✅ Admin
Monitoring
⏸ Autoreply
⏸ Helpdesk
⏸ Broadcast
```

### 21.11 Maintenance — `/maintenance`, `/maintenance on`, `/maintenance off`

Saat maintenance: command user ditolak secara sopan, command admin tetap aktif, game baru tidak dapat dibuat, game yang sedang aktif dapat diselesaikan atau dibatalkan berdasarkan konfigurasi.

### 21.12 Backup — `/backup` (hanya superadmin)

```
✅ Backup berhasil
File  : bot-20260803-134900.db
Ukuran: 3,8 MB
Waktu : 3 Agustus 2026 13.49 WIB
```

Jangan mengirim file database melalui Telegram secara default. Backup disimpan lokal lalu disalin melalui SSH/SCP.

## 22. Admin Menu Berbasis Tombol

`/admin` menjadi pintu utama sehingga admin tidak perlu menghafal semua command.

```
🛠 ADMIN PANEL
[📊 Dashboard] [👥 Users]
[🏘 Groups] [🎮 Games]
[🩺 Health] [⚠ Errors]
[🧩 Features] [⚙ Settings]
```

Callback data: `admin:dashboard`, `admin:users:1`, `admin:users:filter:active:1`, `admin:user:view:128`, `admin:groups:1`, `admin:group:view:7`, `admin:games:active:1`, `admin:game:view:42`, `admin:health`, `admin:features`.

## 23. Middleware Utama

**Database middleware**:

```python
class DatabaseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with self.session_factory() as session:
            data["db_session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
```

**User tracking middleware**: upsert user, memperbarui data profil, mencatat `last_seen`, memeriksa banned status, menyediakan current user kepada handler.

**Group tracking middleware**: upsert grup, menghubungkan user dengan grup, mencatat aktivitas grup, memperbarui nama grup.

**Admin context middleware**: membaca role aplikasi, memasukkan permission ke handler context, menolak akses yang tidak sah.

**Performance middleware**: mengukur `processing_time_ms`, `handler_name`, `module_name`, `success`/`error`.

## 24. Recovery Setelah Restart

Server Android dapat restart karena listrik, memory pressure, atau update. Saat aplikasi mulai:

1. Inisialisasi database.
2. Jalankan pemeriksaan migration.
3. Daftarkan seluruh game.
4. Cari game session yang masih aktif.
5. Evaluasi setiap session.
6. Buat ulang timer yang masih valid.
7. Batalkan session yang tidak dapat dipulihkan.
8. Mulai long polling.
9. Kirim notifikasi startup ke superadmin.

**Recovery lobby**: `LOBBY` dan belum kedaluwarsa → pulihkan timer. `LOBBY` sudah kedaluwarsa dan pemain kurang → batalkan. `LOBBY` sudah kedaluwarsa dan pemain cukup → mulai game atau batalkan sesuai kebijakan.

**Recovery game berjalan (versi pertama)**: untuk tahap awal, `RUNNING` setelah restart → status `ABORTED` → kirim pemberitahuan ke grup → grup dapat memulai game baru. Desain `restore()` tetap tersedia agar game berikutnya dapat mendukung recovery penuh.

## 25. Global Error Handling

```python
@router.errors()
async def global_error_handler(event: ErrorEvent):
    error_reference = generate_error_reference()
    logger.exception(
        "Unhandled update. reference=%s",
        error_reference,
        exc_info=event.exception,
    )
    await monitoring_service.record_error(
        reference=error_reference,
        exception=event.exception,
        update=event.update,
    )
    if event.update.message:
        await event.update.message.answer(
            "Terjadi kesalahan pada bot.\n"
            f"Referensi: {error_reference}"
        )
```

Kategori exception: `GameNotFoundError`, `ActiveGameExistsError`, `LobbyExpiredError`, `PlayerAlreadyJoinedError`, `PlayerLimitReachedError`, `InsufficientPlayersError`, `PermissionDeniedError`, `FeatureDisabledError`, `SessionNotFoundError`, `InvalidGameStateError`.

## 26. Logging

Gunakan structured log. Contoh field: `timestamp`, `level`, `module`, `handler`, `telegram_user_id`, `telegram_chat_id`, `game_session_id`, `event`, `duration_ms`, `error_reference`.

File: `logs/app.log`, `logs/error.log`, `logs/audit.log`.

Retensi awal: Application log 14 hari, Error log 30 hari, Audit log DB 1 tahun, System metrics 30 hari.

Jangan menyimpan: bot token, isi `.env`, seluruh pesan private, data sensitif yang tidak diperlukan.

## 27. Monitoring Internal

Tidak perlu Prometheus pada versi awal. Gunakan kombinasi: database metrics + file logging + command `/health` + startup/shutdown notification + error notification ke superadmin.

Metric awal: `bot_started_at`, `last_update_at`, `updates_processed_total`, `commands_processed_total`, `errors_total`, `active_games`, `active_lobbies`, `registered_users`, `active_users_24h`, `registered_groups`, `database_size`, `disk_free`, `memory_usage`.

## 28. SQLite Configuration

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

Gunakan satu proses bot yang mengakses database tersebut.

```
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
```

## 29. Konfigurasi Aplikasi

`.env.example`:

```
APP_NAME=TelegramMultiBot
APP_ENV=development
APP_VERSION=0.1.0
TIMEZONE=Asia/Jakarta

TELEGRAM_BOT_TOKEN=
TELEGRAM_SUPERADMIN_IDS=
TELEGRAM_DROP_PENDING_UPDATES=false

DATABASE_URL=sqlite+aiosqlite:///data/bot.db

LOG_LEVEL=INFO
LOG_RETENTION_DAYS=14

FEATURE_GAMES=true
FEATURE_ADMIN=true
FEATURE_AUTOREPLY=false
FEATURE_HELPDESK=false
FEATURE_BROADCAST=false

DEFAULT_LOBBY_TIMEOUT_SECONDS=60
DEFAULT_START_COUNTDOWN_SECONDS=5

MAINTENANCE_MODE=false
```

Konfigurasi rahasia tetap di `.env`. Konfigurasi operasional dapat disimpan di tabel `settings`.

## 30. Development di Windows

Gunakan dua bot: development bot (dijalankan dari Windows) dan production bot (dijalankan dari Android TV box). Jangan memakai token yang sama secara bersamaan untuk dua proses long polling.

Setup:

```bash
git clone <repository-url>
cd telegram-multibot
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
python -m app.main
```

## 31. Branching dan Deployment

```
feature/*
   │
   ▼
develop
   │
   ▼
pengujian
   │
   ▼
main
   │
   ▼
tag v0.1.0
   │
   ▼
deploy ke TV box
```

Alur produksi: VS Code Windows → commit → Git repository → `git pull` → Android TV Box → migration → restart service.

Jangan melakukan auto-deploy setiap push ke `main`.

## 32. Deployment ke Termux

```bash
pkg update
pkg upgrade
pkg install python git openssh sqlite termux-services

mkdir -p "$HOME/apps"
cd "$HOME/apps"
git clone <repository-url> telegram-multibot
cd telegram-multibot

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
```

## 33. Service Termux

File: `$PREFIX/var/service/telegram-bot/run`

```sh
#!/data/data/com.termux/files/usr/bin/sh
APP_DIR="$HOME/apps/telegram-multibot"
cd "$APP_DIR"
exec "$APP_DIR/.venv/bin/python" \
  -m app.main 2>&1
```

Aktifkan:

```bash
chmod +x "$PREFIX/var/service/telegram-bot/run"
sv-enable telegram-bot
sv up telegram-bot
```

Operasi:

```bash
sv status telegram-bot
sv restart telegram-bot
sv down telegram-bot
```

## 34. Deployment Script

```bash
#!/data/data/com.termux/files/usr/bin/bash
set -e

APP_DIR="$HOME/apps/telegram-multibot"
VENV_DIR="$APP_DIR/.venv"
cd "$APP_DIR"

echo "Stopping bot..."
sv down telegram-bot

echo "Creating database backup..."
bash scripts/backup.sh

echo "Pulling release..."
git pull --ff-only

echo "Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt

echo "Applying migrations..."
alembic upgrade head

echo "Starting bot..."
sv up telegram-bot

echo "Checking service..."
sv status telegram-bot
```

## 35. Backup Database

```bash
#!/data/data/com.termux/files/usr/bin/bash
set -e

APP_DIR="$HOME/apps/telegram-multibot"
DATABASE="$APP_DIR/data/bot.db"
BACKUP_DIR="$APP_DIR/data/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

sqlite3 "$DATABASE" \
  ".backup '$BACKUP_DIR/bot-$TIMESTAMP.db'"

find "$BACKUP_DIR" \
  -type f \
  -name "bot-*.db" \
  -mtime +14 \
  -delete
```

Strategi: backup lokal setiap hari, salinan ke Windows setiap minggu, retensi lokal 14 hari, restore test setiap bulan.

## 36. Testing

**Unit test**: game registry, game metadata validation, lobby join, lobby leave, minimum player, maximum player, status transition, permission checks, admin pagination, monitoring calculations.

**Integration test**: create lobby → join → start, lobby timeout → cancel, two simultaneous joins, only one game per group, different groups run simultaneously, admin sees active games, admin cancels game, restart recovery.

**Critical test scenario**:
1. Dua user join bersamaan.
2. Pemain keluar saat countdown.
3. Callback dari lobby lama ditekan.
4. Bot restart ketika lobby aktif.
5. Admin membatalkan saat game mulai.
6. Database gagal menulis.
7. Telegram gagal mengedit lobby message.
8. Nama user berubah.
9. Bot dikeluarkan dari grup.
10. Game baru dimulai saat session lama berstatus gagal.

## 37. Scope Versi Pertama

**Harus tersedia**: fondasi aiogram, configuration, SQLite + SQLAlchemy, Alembic migrations, user tracking, group tracking, role & permission admin, admin dashboard, daftar & detail pengguna, daftar & detail grup, monitoring game aktif, health check, feature registry, game registry, `BaseGame` contract, `GameManager`, lobby umum, join & leave, minimum & maksimum pemain, lobby timeout, countdown, satu game aktif per grup, timer registry, lock per session, recovery lobby, global error handler, audit log, satu game sederhana, Termux service, backup & deploy script.

**Belum diimplementasikan tetapi fondasinya tersedia**: game tambahan, autoreply, helpdesk relay, broadcast, leaderboard, ranking, reward system, tournament, web admin, AI integration, scheduled messages, moderation tools.

## 38. Roadmap Implementasi

**Fase 1 — Foundation**: project setup, configuration, logging, database, Alembic, bot bootstrap, middleware, user tracking, group tracking.

**Fase 2 — Admin monitoring**: role admin, `/admin` dashboard, `/users`, `/user`, `/groups`, `/group`, `/health`, `/errors`, audit log, pagination.

**Fase 3 — Game engine**: `BaseGame`, `GameRegistry`, `GameManager`, `LobbyService`, `TimerRegistry`, `GameLockManager`, game session repository, recovery service.

**Fase 4 — Game pertama**: metadata, initial state, lobby, gameplay, timeout, winner, finish result, event log.

**Fase 5 — Production operation**: Termux installation, runit service, Termux:Boot, deploy script, backup, restore test, startup notification, health monitoring.

**Fase 6 — Fitur lanjutan**: game kedua, autoreply, helpdesk, leaderboard, broadcast, moderation.

## 39. Keputusan Final Baseline

| Keputusan | Nilai |
|---|---|
| Arsitektur | Modular monolith |
| Game concurrency | Satu game aktif per grup |
| Antargrup | Dapat berjalan bersamaan |
| User tracking | Berdasarkan interaksi yang diterima bot |
| Admin interface | Private chat + inline keyboard |
| Admin identity | Numeric Telegram user ID |
| Game lifecycle | Lobby → Starting → Running → Finished |
| Lobby minimum | Ditentukan per game |
| Lobby maksimum | Ditentukan per game |
| Lobby timeout | Default 60 detik |
| Start countdown | Default 5 detik |
| State storage | SQLite JSON + kolom terstruktur |
| Timer | `asyncio.Task` + absolute timestamp |
| Concurrency protection | `asyncio.Lock` per session |
| Migration | Alembic |
| Production process | Satu bot process |
| Recovery lobby | Ya |
| Recovery running game v1 | Abort secara aman |
| Development bot | Terpisah |
| Production deployment | Git tag + SSH deploy |
| Monitoring | Admin command + database metrics |

Dengan blueprint ini, project pertama tetap kecil — satu game sederhana — tetapi fondasinya sudah siap untuk menambahkan banyak game dan fungsi non-game tanpa merombak struktur utama.
