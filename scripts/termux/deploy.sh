#!/data/data/com.termux/files/usr/bin/bash
# Update manual ke versi terbaru -- lihat docs/termux-deployment-guide.md
# langkah 6. SENGAJA tidak otomatis (tidak ada trigger dari git push) --
# jalankan ini sendiri kapan mau update.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$APP_DIR"

echo "Menghentikan service..."
sv down telegram-bot

echo "Membuat backup database..."
bash scripts/termux/backup.sh

echo "Mengambil update dari git..."
git pull --ff-only

echo "Install dependency..."
"$APP_DIR/.venv/bin/pip" install --no-cache-dir -r requirements.txt

echo "Menjalankan migration..."
"$APP_DIR/.venv/bin/python" -m alembic upgrade head

echo "Menyalakan service..."
sv up telegram-bot

echo "Status akhir:"
sv status telegram-bot
