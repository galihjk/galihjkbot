from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """UTC saat ini, naive (tanpa tzinfo).

    SQLite membuang tzinfo saat datetime dibaca ulang dari database, jadi
    seluruh kode menyimpan dan membandingkan datetime dalam bentuk naive-UTC
    supaya tidak terjadi "can't subtract offset-naive and offset-aware
    datetimes" saat data lama dibaca dari sesi baru.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def humanize_relative(moment: datetime) -> str:
    delta_seconds = int((utcnow() - moment).total_seconds())
    if delta_seconds < 0:
        delta_seconds = 0

    if delta_seconds < 60:
        return "baru saja"

    minutes = delta_seconds // 60
    if minutes < 60:
        return f"{minutes} menit lalu"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} jam lalu"

    days = hours // 24
    return f"{days} hari lalu"
