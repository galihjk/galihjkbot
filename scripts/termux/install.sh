#!/data/data/com.termux/files/usr/bin/bash
# Instalasi awal bot di Termux. Idempotent -- aman dijalankan ulang kalau
# terputus di tengah. Jalankan dari root project:
#   bash scripts/termux/install.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$APP_DIR"

echo "Membuat virtualenv (.venv)..."
if [ ! -d ".venv" ]; then
  python -m venv .venv
else
  echo "  .venv sudah ada, dilewati."
fi

echo "Install dependency..."
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install --no-cache-dir -r requirements.txt

if [ ! -f ".env" ]; then
  echo "Menyalin .env.example -> .env ..."
  cp .env.example .env
  echo ""
  echo "PENTING: edit .env sekarang, isi minimal TELEGRAM_BOT_TOKEN dan TELEGRAM_SUPERADMIN_IDS."
  echo "  nano .env"
else
  echo ".env sudah ada, tidak ditimpa."
fi

echo ""
echo "Instalasi selesai. Langkah selanjutnya:"
echo "  1. Isi .env kalau belum (lihat docs/termux-deployment-guide.md langkah 3)"
echo "  2. source .venv/bin/activate && alembic upgrade head"
echo "  3. Pasang service (lihat docs/termux-deployment-guide.md langkah 5)"
