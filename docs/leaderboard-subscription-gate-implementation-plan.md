# Gating Leaderboard Global lewat Subscribe Channel — Implementation Plan

**Status: ✅ SELESAI dari sisi kode/test.** Belum diverifikasi manual di Telegram sungguhan (lihat §7). Riwayat keputusan lengkap ada di `development-history.md` (entri "Gating leaderboard global lewat subscribe channel + `MaintenanceGate`").

## 1. Tujuan

Skor user hanya boleh masuk **leaderboard GLOBAL bulanan** (posting ke channel + `/leaderboard` on-demand) kalau user itu subscribe channel leaderboard. `/skor` jadi titik edukasi: kasih tahu status subscribe user + link kalau belum. **Leaderboard per-grup** (`/leaderboardgrup`, posting per-grup saat reset bulanan) **sama sekali tidak terpengaruh** — tetap menghitung semua member grup seperti sebelumnya.

Dua keputusan produk dikonfirmasi lewat `AskUserQuestion` sebelum coding:

1. `/leaderboard` (global, on-demand) **juga** ikut difilter — bukan cuma pengumuman bulanan, supaya tidak ada user yang bingung kenapa dia muncul di `/leaderboard` tapi hilang dari pengumuman channel.
2. Status subscribe **di-re-verify LIVE ke Telegram tepat saat job bulanan berjalan** (bukan cuma cache lama dari `/skor`), dengan syarat tambahan: job harus tahan-gagal (1 user gagal cek tidak boleh membatalkan job), dan selama job berjalan **user tidak boleh mulai game baru** & **autoreply dimatikan sementara** — mencegah aktivitas yang bersinggungan dengan proses rekap.

## 2. Ruang lingkup

**Termasuk:**

- Kolom baru `users.is_leaderboard_channel_subscribed` (cache status subscribe, di-refresh di dua titik: saat `/skor` dipanggil, dan saat job bulanan re-verifikasi tiap user).
- `/skor`: cek live status subscribe ke channel (`bot.get_chat_member`), update cache, tampilkan notice (belum subscribe + link, atau sudah subscribe → info ikut global).
- `/leaderboard`: filter cuma user dengan cache `is_leaderboard_channel_subscribed = True`.
- `run_monthly_maintenance()`: re-verify live status SEMUA user berskor bulan itu (bukan cuma yang cache-nya `True`, supaya user yang subscribe belakangan tanpa pernah `/skor` tetap tercatat), refresh cache, lalu HANYA posting yang lolos verifikasi ke channel. `sum_scores_by_group`, posting per-grup, dan `delete_scores_in_range` (reset) **tidak diubah** — semua skor tetap dihapus untuk semua user, subscribe cuma soal siapa yang MUNCUL di pengumuman channel.
- `MaintenanceGate`: flag in-memory, `True` selama job bulanan benar-benar mengerjakan (re-verify → posting → delete → cleanup), dibaca handler mulai-game (`/game`, klik menu game) dan autoreply untuk menolak sementara. Selalu dilepas lewat `try/finally` walau job error di tengah jalan.

**Belum termasuk (di luar scope):**

- Membekukan game yang SUDAH berjalan/lobby yang sudah ada saat maintenance mulai — hanya pembuatan lobby BARU yang diblokir. Game yang sudah jalan boleh selesai normal (skornya tercatat di bulan berikutnya, tidak bersinggungan dengan window yang sedang direset).
- Notifikasi real-time Telegram (`chat_member` update) saat user subscribe/unsubscribe — status tetap dicek on-demand (saat `/skor` atau job bulanan), bukan push event.
- `/skor` sendiri TIDAK diblokir saat maintenance (read-only + cache-write ringan, aman dipanggil kapan saja).

## 3. Perubahan data model

`app/database/models/user.py` — kolom baru:

```python
is_leaderboard_channel_subscribed: Mapped[bool] = mapped_column(default=False, nullable=False)
```

Migration `db0771366137_add_users_is_leaderboard_channel_.py`:

```python
op.add_column(
    "users",
    sa.Column(
        "is_leaderboard_channel_subscribed",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ),
)
```

## 4. `MaintenanceGate`

`app/core/maintenance.py` — flag boolean sederhana, bukan `asyncio.Lock`:

```python
class MaintenanceGate:
    def __init__(self) -> None:
        self.active = False

MAINTENANCE_NOTICE = "⏳ Nanti dulu ya, lagi rekap skor bulanan. Coba lagi beberapa menit lagi."
```

Instansiasi sekali di `app/main.py`, disebar lewat dua jalur:
- `dispatcher["maintenance_gate"] = maintenance_gate` (pola sama seperti `dispatcher["settings"]`) — otomatis ter-inject ke handler manapun yang punya parameter `maintenance_gate: MaintenanceGate`.
- `run_leaderboard_scheduler(bot, session_factory, settings, maintenance_gate)` → diteruskan ke `run_monthly_maintenance(...)`.

Dibaca di tiga titik:
- `app/modules/games/handlers/commands.py::handle_game_command` & `handle_game_menu_selection` — balas `MAINTENANCE_NOTICE` & `return` sebelum logic apa pun kalau `maintenance_gate.active`. `/games` (list), `/gamestatus`, `/cancelgame` **tidak diblokir** (bukan aksi mulai game baru).
- `app/modules/autoreply/handlers.py::handle_autoreply_message` — `return` diam-diam (tanpa balasan, sesuai sifat autoreply yang pasif) kalau gate aktif.

## 5. Alur `/skor`

`app/modules/leaderboard/handlers.py::handle_skor` — tambah parameter `bot: Bot`. Kalau `settings.telegram_leaderboard_channel_id` terisi:

1. Panggil `bot.get_chat_member(channel_id, current_user.telegram_user_id)`.
2. `is_subscribed = member.status in {MEMBER, ADMINISTRATOR, CREATOR}` (status lain seperti `LEFT`/`KICKED` = tidak subscribe).
3. Sukses → mutasi langsung `current_user.is_leaderboard_channel_subscribed = is_subscribed` (objek ORM yang sama sudah di-inject sebagai `current_user`, commit otomatis lewat `DatabaseMiddleware` yang sudah ada — tidak perlu commit manual).
4. Gagal (exception, misal bot bukan admin / user belum pernah interaksi) → log warning, cache LAMA dipertahankan, notice dibuat dari nilai cache lama.
5. Tempel `presenters.format_subscription_notice(is_subscribed, channel_link)` ke balasan.

Kalau channel belum dikonfigurasi (`channel_id is None`), seluruh langkah ini di-skip — perilaku lama, tanpa notice.

## 6. Alur `/leaderboard` & job bulanan

**`/leaderboard`** (`handle_leaderboard`): query diganti dari `sum_global_scores_by_user` ke `sum_global_scores_by_user_subscribed` (filter `WHERE is_leaderboard_channel_subscribed = True`, cache-based, TANPA panggilan Telegram API — supaya cepat & tidak kena rate limit di command on-demand).

**`run_monthly_maintenance()`** (`app/modules/leaderboard/service.py`):

```text
has_run? ── ya ──> skip
   │ tidak
   ▼
ambil global_rows MENTAH (sum_global_scores_by_user, semua user berskor)
   │
   ▼
maintenance_gate.active = True ──┐
   │                              │ (try/finally, gate PASTI lepas)
   ▼                              │
loop tiap user: get_chat_member   │
  sukses → cache_updates.append   │
  gagal  → log warning, dianggap  │
           TIDAK subscribe siklus │
           ini SAJA (cache lama   │
           dipertahankan)         │
  throttle 0.1s/panggilan         │
   │                              │
   ▼                              │
batch commit cache_updates        │
   │                              │
   ▼                              │
post channel: subscribed_rows saja│  ── gagal? → return (job dibatalkan,
   │  (+ ranking antar-grup,           tidak ada data dihapus, dicoba
   │   TIDAK difilter)                 lagi besok)
   ▼                              │
post per-grup (SEMUA member,      │  ── 1 grup gagal → log, lanjut
   TIDAK difilter subscribe)      │     (tidak fatal)
   ▼                              │
delete_scores_in_range (SEMUA     │
   user, terlepas status          │
   subscribe) + mark_run          │
   ▼                              │
cleanup user/grup tidak aktif ────┘
   │
   ▼
maintenance_gate.active = False (finally)
```

Konstanta baru di `service.py`: `_SUBSCRIBED_STATUSES = {MEMBER, ADMINISTRATOR, CREATOR}`, `_SUBSCRIPTION_CHECK_DELAY_SECONDS = 0.1` (throttle, cegah flood limit Telegram saat user banyak).

## 7. Test plan (sudah dijalankan, semua lolos)

`tests/modules/leaderboard/` (baru, 22 test — sebelumnya modul leaderboard belum punya test formal sama sekali):

- `test_repository.py`: `sum_global_scores_by_user_subscribed` cuma mengembalikan user `True`; `sum_global_scores_by_user` (mentah) tetap mengembalikan semua; `set_channel_subscription` mengubah flag dengan benar.
- `test_service.py`: posting channel cuma berisi user yang lolos re-verifikasi LIVE (bukan cache lama); cache di-refresh utk cek yang sukses, TIDAK berubah utk cek yang gagal (exception); kegagalan posting channel tetap membatalkan seluruh job (regresi, skor tidak terhapus); kegagalan 1 grup tidak membatalkan job (regresi); leaderboard grup & delete tetap mencakup SEMUA user; `maintenance_gate.active` True selama proses, False lagi setelahnya — TERMASUK saat dipaksa exception tak terduga via `monkeypatch` (membuktikan `finally` benar-benar lepas gate); channel belum dikonfigurasi / periode sudah pernah jalan → skip total tanpa side effect.
- `test_handlers.py`: `/skor` 3 skenario (belum subscribe+link, sudah subscribe, gagal cek→fallback cache lama tanpa crash, channel tidak dikonfigurasi→tanpa notice); `/leaderboard` cuma menampilkan subscriber.

`tests/modules/games/test_maintenance_gate.py` & `tests/modules/autoreply/test_maintenance_gate.py`: gate aktif → mulai-game/autoreply diblokir (tanpa lobby terbuat / tanpa balasan autoreply); gate tidak aktif → perilaku normal (regresi).

Regresi: seluruh test suite (223 test) dijalankan ulang setelah semua perubahan, semua lolos.

## 8. Definition of Done

- [x] Kolom + migration `is_leaderboard_channel_subscribed` jalan (`alembic upgrade head` sukses).
- [x] `/skor` menampilkan notice benar sesuai status subscribe, cache ter-update, tahan error `get_chat_member`.
- [x] `/leaderboard` cuma menampilkan subscriber; `/leaderboardgrup` tidak tersentuh sama sekali.
- [x] Job bulanan re-verify live, posting channel cuma subscriber, posting grup & delete tetap untuk semua user, kegagalan per-user/per-grup tidak fatal, kegagalan channel tetap fatal (regresi).
- [x] `MaintenanceGate` memblokir mulai-game & autoreply selama job jalan, selalu lepas walau error.
- [x] Test otomatis lengkap (22 test baru) + regresi test suite penuh (223 test) lolos.
- [ ] **Uji manual Telegram nyata** (langkah lanjutan, dicatat di `project-status.md`): bot jadi admin channel `GalihJK Bot Development` (`-1001126002148`), 1 user subscribe & 1 belum, jalankan `/skor` masing-masing, trigger job bulanan sungguhan, pastikan cuma subscriber muncul di pengumuman channel sementara leaderboard grup tetap lengkap.
