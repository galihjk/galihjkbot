from __future__ import annotations


class MaintenanceGate:
    """Flag proses global, `True` selama job pemeliharaan leaderboard bulanan
    (`run_monthly_maintenance`) sedang re-verify subscribe + posting + reset
    skor -- dibaca handler mulai-game & autoreply supaya tidak ada aktivitas
    baru yang bersinggungan dengan proses rekap. Plain bool cukup (bukan
    `asyncio.Lock`) karena cuma dibaca/ditulis dalam event loop yang sama."""

    def __init__(self) -> None:
        self.active = False


MAINTENANCE_NOTICE = (
    "⏳ Nanti dulu ya, lagi rekap skor bulanan. Coba lagi beberapa menit lagi."
)
