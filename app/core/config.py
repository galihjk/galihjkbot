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
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.load()
