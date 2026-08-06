from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _resolve_database_url() -> URL:
    raw = os.getenv("DATABASE_URL", "").strip()
    if raw:
        return make_url(raw)

    default_db_path = BASE_DIR / "data" / "bot.db"
    return URL.create(
        drivername="sqlite+aiosqlite",
        database=str(default_db_path),
    )


def _parse_ids(raw: str) -> list[int]:
    return [int(value) for value in raw.split(",") if value.strip()]


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_version: str
    timezone: str
    telegram_bot_token: str
    telegram_superadmin_ids: list[int]
    telegram_drop_pending_updates: bool
    telegram_leaderboard_channel_id: int | None
    telegram_leaderboard_channel_link: str | None
    database_url: URL
    log_level: str
    autoreply_source_url: str
    autoreply_startup_sync: bool
    autoreply_sync_interval_seconds: int
    autoreply_http_connect_timeout_seconds: float
    autoreply_http_read_timeout_seconds: float
    autoreply_max_source_bytes: int
    autoreply_max_responses_per_message: int
    autoreply_keep_snapshots: int
    autoreply_allow_private: bool
    autoreply_ignore_bots: bool

    @classmethod
    def load(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN belum diset. Salin .env.example menjadi "
                ".env lalu isi token bot."
            )
        channel_id_raw = os.getenv("TELEGRAM_LEADERBOARD_CHANNEL_ID", "").strip()
        channel_link_raw = os.getenv("TELEGRAM_LEADERBOARD_CHANNEL_LINK", "").strip()
        return cls(
            app_name=os.getenv("APP_NAME", "TelegramMultiBot"),
            app_env=os.getenv("APP_ENV", "development"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            timezone=os.getenv("TIMEZONE", "Asia/Jakarta"),
            telegram_bot_token=token,
            telegram_superadmin_ids=_parse_ids(
                os.getenv("TELEGRAM_SUPERADMIN_IDS", "")
            ),
            telegram_drop_pending_updates=_parse_bool(
                os.getenv("TELEGRAM_DROP_PENDING_UPDATES", "false")
            ),
            telegram_leaderboard_channel_id=(
                int(channel_id_raw) if channel_id_raw else None
            ),
            telegram_leaderboard_channel_link=channel_link_raw or None,
            database_url=_resolve_database_url(),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            autoreply_source_url=os.getenv("AUTOREPLY_SOURCE_URL", "").strip(),
            autoreply_startup_sync=_parse_bool(
                os.getenv("AUTOREPLY_STARTUP_SYNC", "true")
            ),
            autoreply_sync_interval_seconds=int(
                os.getenv("AUTOREPLY_SYNC_INTERVAL_SECONDS", "0")
            ),
            autoreply_http_connect_timeout_seconds=float(
                os.getenv("AUTOREPLY_HTTP_CONNECT_TIMEOUT_SECONDS", "5")
            ),
            autoreply_http_read_timeout_seconds=float(
                os.getenv("AUTOREPLY_HTTP_READ_TIMEOUT_SECONDS", "15")
            ),
            autoreply_max_source_bytes=int(
                os.getenv("AUTOREPLY_MAX_SOURCE_BYTES", "5242880")
            ),
            autoreply_max_responses_per_message=int(
                os.getenv("AUTOREPLY_MAX_RESPONSES_PER_MESSAGE", "20")
            ),
            autoreply_keep_snapshots=int(
                os.getenv("AUTOREPLY_KEEP_SNAPSHOTS", "3")
            ),
            autoreply_allow_private=_parse_bool(
                os.getenv("AUTOREPLY_ALLOW_PRIVATE", "false")
            ),
            autoreply_ignore_bots=_parse_bool(
                os.getenv("AUTOREPLY_IGNORE_BOTS", "true")
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.load()
