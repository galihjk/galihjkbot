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

### ⚠️ Storage internal Android TV Box kecil (< 1-2 GB bebas) — urutan yang disarankan

`aiogram` menarik beberapa dependency yang punya extension bukan-Python-murni: `pydantic` v2 (lewat `pydantic-core`, ditulis Rust) dan `aiohttp` (lewat `multidict`/`frozenlist`/`yarl`, C extension). Termux memakai Android Bionic libc (bukan glibc), jadi wheel prebuilt resmi (`manylinux`) di PyPI tidak akan pernah cocok — `pip` selalu jatuh ke build-from-source, dan toolchain buat build itu (`rust`, ratusan MB terinstall) bisa langsung menghabiskan storage di TV box yang sisa ruangnya sudah tipis SEBELUM instalasi apa pun dimulai. Kalau device kamu termasuk kategori ini, jangan langsung `pkg install rust binutils` — ikuti urutan di bawah dari yang termurah dulu.

(`tzdata` juga ada di `requirements.txt` sejak fitur leaderboard bulanan ditambahkan — ini paket data murni Python, TIDAK ada extension, tidak menambah risiko build apa pun.)

**1. Bebaskan storage Android dulu, sebelum install apa pun.**

```bash
df -h "$HOME"
```

Kalau hasilnya < 1-2 GB, storage Android-nya sendiri (bukan cuma bagian Termux) kemungkinan sudah sesak. Cek di Settings > Storage / Apps TV box: clear cache aplikasi bawaan, uninstall/disable bloatware pre-installed yang tidak dipakai, hapus file OTA update yang sudah terpasang. Ini housekeeping Android biasa, sering jadi sumber ruang terbesar yang bisa direbut tanpa risiko apa pun.

**2. Clone hemat + install tanpa cache pip.**

```bash
git clone --depth 1 <URL_REPOSITORY_KAMU> telegram-multibot   # skip histori git
```

`scripts/termux/install.sh` dan `scripts/termux/deploy.sh` sudah pakai `pip install --no-cache-dir` — pip secara default menyimpan cache wheel/sdist yang bisa nambah puluhan-ratusan MB peak usage pas install padahal begitu terpasang tidak dipakai lagi.

**3. Skip Rust dari awal — jangan tunggu gagal dulu.**

Untuk device dengan storage < 1-2 GB, langsung pakai wheel prebuilt `pydantic-core` SEBELUM coba `pkg install rust binutils` sama sekali — jangan habiskan storage buat toolchain yang kemungkinan besar gagal fit, baru ketahuan setelah storage sudah terpakai separuh jalan. Proyek pihak ketiga [`Eutalix/android-pydantic-core`](https://github.com/Eutalix/android-pydantic-core) menyediakan wheel `pydantic-core` prebuilt khusus Termux/Android (ARM64/ARMv7), jauh lebih kecil dan tidak butuh Rust:

```bash
pip install pydantic-core --extra-index-url https://eutalix.github.io/android-pydantic-core/
bash scripts/termux/install.sh
```

**Catatan:** ini sumber pihak ketiga, bukan PyPI/pydantic resmi — pakai sesuai penilaian risiko sendiri. Kalau ragu, lebih aman bersihkan storage dan tetap build lewat `rust` resmi (langkah di bawah).

**4. Kalau paket LAIN (bukan `pydantic-core`) juga gagal build.**

`multidict`/`yarl`/`frozenlist` (dari `aiohttp`, ditarik `aiogram`) dan `greenlet` (dari `sqlalchemy[asyncio]`) punya masalah sama — wheel manylinux resmi tidak cocok di Bionic libc. Beda dari `pydantic-core`, ini cuma butuh C compiler, jauh lebih kecil dari Rust:

```bash
pkg install clang
pip install --no-cache-dir -r requirements.txt
```

**5. Kalau masih perlu Rust juga** (jarang, tapi kalau wheel Eutalix di atas ternyata tidak cocok versi Python/arsitektur kamu):

```bash
pkg install rust binutils
```

Kalau ini gagal dengan "No space left on device" (biasanya error di tengah unpack seperti `cannot copy extracted data for '...rmeta' ... failed to write`):

```bash
pkg clean
pkg autoclean
pkg install rust binutils   # ulangi
```

**6. Bersih-bersih rutin setelah install** (baik berhasil maupun gagal di tengah) — jangan cuma pas troubleshooting, cache ini balik numpuk tiap kali `deploy.sh` jalan `pip install` ulang:

```bash
pip cache purge
pkg clean && pkg autoclean
rm -rf ~/.cache/pip
```

**7. Kalau semua di atas masih belum cukup — expand storage lewat Adoptable Storage.**

Ini BEDA dari peringatan WAL di langkah 3 di atas (soal shared media storage `/sdcard/...`, filesystem FAT/exFAT tanpa POSIX locking yang benar). "Adoptable Storage" adalah fitur Android (Settings > Storage > pilih USB/microSD yang ditancapkan > "Format as internal" / "Set up as internal storage") yang memformat drive itu jadi filesystem asli (ext4/f2fs) dan digabung TRANSPARAN ke internal storage oleh OS — Termux melihatnya sebagai storage internal biasa (bukan shared storage), sehingga file locking WAL SQLite seharusnya tetap aman selama benar-benar "adopted" (bukan cuma dipasang sebagai storage USB shared biasa).

- Syarat: TV box punya port USB/microSD, Android-nya tidak mem-disable fitur ini (sebagian OEM TV box murah menonaktifkan), device di-restart setelah setup.
- Verifikasi setelah setup: `df -h "$HOME"` harus menunjukkan kapasitas baru yang jauh lebih besar — kalau tidak berubah, adoptable storage belum benar-benar aktif untuk partisi Termux, JANGAN lanjut instalasi (baca ulang langkah 3 di dokumen ini soal risiko WAL).
- Ini butuh drive USB/SD fisik tambahan, dan format drive itu akan MENGHAPUS data di dalamnya. Tidak dijamin didukung semua firmware TV box — kalau device tidak mendukung, ini jalan buntu di device ini (bukan sesuatu yang dipaksakan lewat root).

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
| `pip install` gagal build | Tidak ada wheel prebuilt utk arm64/Bionic libc | Lihat bagian "Storage internal Android TV Box kecil" di atas — kalau storage terbatas, coba wheel Eutalix dulu sebelum `pkg install rust binutils` |
| Bot tidak membalas `/start` | Service belum jalan / token salah | `sv status telegram-bot`, cek `logs/error.log` |
| "database is locked" terus-menerus | DB di shared storage (WAL tidak didukung) | Pastikan `DATABASE_URL` kosong / mengarah ke `data/bot.db` di storage privat |
| Bot mati sendiri setelah beberapa jam | Android mematikan proses Termux di background | Pastikan wakelock aktif + battery optimization "unrestricted" |
| `alembic upgrade head` error "no module named app" | Dijalankan bukan dari root project | `cd` dulu ke `~/apps/telegram-multibot` |
