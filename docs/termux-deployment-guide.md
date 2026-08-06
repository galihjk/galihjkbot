# Panduan Deployment ke Termux (Android TV Box)

Panduan ini untuk dijalankan **manual, langkah demi langkah, di device Android TV Box sungguhan** lewat Termux. Tidak ada asisten AI di device itu — ikuti persis, dan kalau ada langkah yang error, catat pesan errornya lalu tanyakan di sesi Claude Code berikutnya (di komputer dev) untuk didiagnosis.

Referensi desain awal: `docs/blueprint.md` §32-35. Script siap pakai ada di `scripts/termux/` (ikut ter-`git pull`, jadi tidak perlu ngetik ulang command panjang).

---

## 0. Sebelum mulai

- **Install Termux dari F-Droid**, BUKAN dari Play Store — versi Play Store sudah tidak dimaintain oleh developernya dan sering gagal `pkg install` paket tertentu. Link: https://f-droid.org/packages/com.termux/
- Supaya Termux tidak dimatikan Android di background (device ini fungsinya jadi server 24 jam):
  - Buka notifikasi Termux yang muncul, tap "Acquire wakelock" (atau jalankan `termux-wake-lock` di Termux).
  - Di setting Android: cari battery optimization / app management untuk Termux, set ke "tidak dibatasi" / "unrestricted" (nama menu beda-beda tiap merk TV Box).
- Kalau device pakai storage eksternal (SD card) sebagai default, pastikan langkah instalasi di bawah TETAP menyimpan project di storage internal Termux (`$HOME`), bukan `/sdcard/...` — lihat peringatan WAL di langkah 3.

## 1. Install paket dasar

```bash
pkg update && pkg upgrade
pkg install python git openssh sqlite termux-services
```

Cek versi Python — project ini ditulis untuk **Python 3.10** (belum pakai fitur 3.11+ seperti `enum.StrEnum`):

```bash
python3 --version
```

Kalau versinya jauh lebih baru (3.12+) dan nanti ada error aneh terkait enum, itu petunjuknya — tapi kemungkinan besar tetap jalan normal karena kode tidak memakai fitur yang benar-benar eksklusif 3.11+.

## 2. Clone & install dependency

```bash
mkdir -p "$HOME/apps"
cd "$HOME/apps"
git clone <URL_REPOSITORY_KAMU> telegram-multibot
cd telegram-multibot

bash scripts/termux/install.sh
```

`install.sh` otomatis membuat virtualenv, install `requirements.txt`, dan menyalin `.env.example` jadi `.env` kalau belum ada. **Idempotent** — aman dijalankan ulang kalau terputus di tengah.

### ⚠️ Kalau `pip install` gagal build (paket Rust/C extension)

`aiogram` menarik beberapa dependency yang punya extension bukan-Python-murni: `pydantic` v2 (lewat `pydantic-core`, ditulis Rust) dan `aiohttp` (lewat `multidict`/`frozenlist`/`yarl`, C extension). Kalau `pip` menemukan wheel prebuilt untuk `aarch64` (Android TV Box biasanya ARM64), instalasi akan instan. Kalau TIDAK ada wheel yang cocok, `pip` akan mencoba build dari source dan gagal kalau compiler belum ada. Solusi:

(`tzdata` juga ada di `requirements.txt` sejak fitur leaderboard bulanan ditambahkan — ini paket data murni Python, TIDAK ada extension, tidak menambah risiko build apa pun, cuma memastikan `zoneinfo` selalu punya data zona waktu yang konsisten lintas platform.)

```bash
pkg install rust binutils
pip install -r requirements.txt
```

Build dari source lewat `rust`/`binutils` akan lebih lambat (beberapa menit), tapi seharusnya berhasil. Kalau tetap gagal, catat pesan error lengkapnya (biasanya nama paket yang gagal ada di baris paling atas traceback pip) untuk didiagnosis lebih lanjut.

## 3. Isi konfigurasi (`.env`)

Edit `.env` (`nano .env` atau `vi .env`):

```
TELEGRAM_BOT_TOKEN=<token dari @BotFather>
TELEGRAM_SUPERADMIN_IDS=<Telegram user ID kamu, numeric>
APP_ENV=production
TELEGRAM_LEADERBOARD_CHANNEL_ID=<ID channel leaderboard, kalau sudah dibuat>
TELEGRAM_LEADERBOARD_CHANNEL_LINK=<link/username channel itu, opsional>
```

**`APP_ENV=production` penting** — ini menyembunyikan game "Test" (`simple_game`) yang sengaja frozen, cuma dipakai buat uji internal.

### ⚠️ Jangan pindahkan database ke shared storage

Default `DATABASE_URL` kosong = pakai `data/bot.db` di dalam folder project (storage privat Termux). **JANGAN** diarahkan ke `/sdcard/...` atau storage eksternal lain — SQLite jalan pakai WAL mode (`journal_mode=WAL`), yang butuh file-locking POSIX yang TIDAK didukung filesystem shared storage Android. Kalau dipindah ke sana, database bisa korup atau error "database is locked" terus-menerus.

## 4. Migration database

```bash
source .venv/bin/activate
alembic upgrade head
```

Jalankan dari root folder project (`~/apps/telegram-multibot`) — `alembic.ini` mengasumsikan working directory ini untuk menemukan modul `app`.

## 5. Pasang sebagai service (`runit`, auto-start & auto-restart)

```bash
mkdir -p "$PREFIX/var/service/telegram-bot"
ln -s "$HOME/apps/telegram-multibot/scripts/termux/telegram-bot.run" \
      "$PREFIX/var/service/telegram-bot/run"
chmod +x "$PREFIX/var/service/telegram-bot/run"
sv-enable telegram-bot
sv up telegram-bot
```

Verifikasi:

```bash
sv status telegram-bot
tail -f "$HOME/apps/telegram-multibot/logs/app.log"
```

Kirim `/start` ke bot dari Telegram — kalau bot membalas, service jalan dengan benar.

Operasi harian:

```bash
sv restart telegram-bot   # restart manual
sv down telegram-bot      # matikan (mis. sebelum backup manual)
sv up telegram-bot        # nyalakan lagi
```

## 6. Update ke versi baru (manual, TIDAK otomatis)

**Sengaja tidak ada auto-deploy tiap push ke `main`** — update dilakukan manual kapan kamu mau, supaya tidak ada perubahan mengejutkan di tengah bot dipakai orang.

```bash
cd "$HOME/apps/telegram-multibot"
bash scripts/termux/deploy.sh
```

Script ini otomatis: matikan service → backup database → `git pull` → install dependency baru → jalankan migration → nyalakan service lagi → tampilkan status akhir.

## 7. Backup database

`deploy.sh` sudah otomatis backup sebelum update, tapi ada baiknya juga backup terjadwal harian:

```bash
bash scripts/termux/backup.sh
```

Backup disimpan di `data/backups/bot-<timestamp>.db`, retensi otomatis 14 hari (file lebih lama dihapus otomatis oleh script yang sama).

Untuk jadwal otomatis harian, tambahkan ke crontab Termux (`pkg install cronie` kalau belum ada `crontab`):

```bash
crontab -e
# tambahkan baris:
0 3 * * * bash $HOME/apps/telegram-multibot/scripts/termux/backup.sh
```

**Strategi backup yang disarankan** (dari `blueprint.md` §35): backup lokal otomatis tiap hari (di atas), salin manual ke Windows/cloud tiap minggu (via `scp`/`termux-share`/upload manual — tidak ada script untuk ini, sengaja manual), dan coba restore test sebulan sekali untuk memastikan backup-nya benar-benar valid.

---

## Troubleshooting cepat

| Masalah | Kemungkinan sebab | Cek |
|---|---|---|
| `pip install` gagal build | Tidak ada wheel prebuilt utk arm64 | `pkg install rust binutils`, install ulang |
| Bot tidak membalas `/start` | Service belum jalan / token salah | `sv status telegram-bot`, cek `logs/error.log` |
| "database is locked" terus-menerus | DB di shared storage (WAL tidak didukung) | Pastikan `DATABASE_URL` kosong / mengarah ke `data/bot.db` di storage privat |
| Bot mati sendiri setelah beberapa jam | Android mematikan proses Termux di background | Pastikan wakelock aktif + battery optimization "unrestricted" |
| `alembic upgrade head` error "no module named app" | Dijalankan bukan dari root project | `cd` dulu ke `~/apps/telegram-multibot` |
