from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")


def _local_now(timezone_name: str) -> datetime:
    return datetime.now(_UTC).astimezone(ZoneInfo(timezone_name))


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(dt: datetime) -> datetime:
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1)
    return dt.replace(month=dt.month + 1)


def _to_naive_utc(dt: datetime) -> datetime:
    """DB (`committed_at`/`last_seen_at`/dst) selalu naive-UTC (lihat
    `app/utils/datetime.py::utcnow`) -- batas periode harus dikonversi ke
    bentuk yang sama supaya bisa dibandingkan langsung di query."""
    return dt.astimezone(_UTC).replace(tzinfo=None)


def period_label(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def current_period_window(timezone_name: str) -> tuple[datetime, datetime, str]:
    """Jendela bulan yang SEDANG berjalan (belum direset) -- dipakai
    query LIVE (`/skor`, `/leaderboard`, `/leaderboardgrup`)."""
    start_local = _month_start(_local_now(timezone_name))
    end_local = _next_month(start_local)
    return _to_naive_utc(start_local), _to_naive_utc(end_local), period_label(start_local)


def previous_period_window(timezone_name: str) -> tuple[datetime, datetime, str]:
    """Jendela bulan yang SUDAH BERAKHIR -- dipakai job pemeliharaan bulanan."""
    this_month_start_local = _month_start(_local_now(timezone_name))
    start_local = _month_start(this_month_start_local - timedelta(days=1))
    end_local = this_month_start_local
    return _to_naive_utc(start_local), _to_naive_utc(end_local), period_label(start_local)


def inactivity_threshold(timezone_name: str, months: int = 6) -> datetime:
    """Batas waktu 'tidak aktif N bulan' dalam bentuk naive-UTC, dihitung
    dari sekarang (bukan dari awal bulan) -- konsisten dengan `last_seen_at`/
    `last_activity_at` yang dicatat kontinu, bukan per-bulan."""
    now_local = _local_now(timezone_name)
    year = now_local.year
    month = now_local.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(now_local.day, calendar.monthrange(year, month)[1])
    threshold_local = now_local.replace(year=year, month=month, day=day)
    return _to_naive_utc(threshold_local)
