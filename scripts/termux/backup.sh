#!/data/data/com.termux/files/usr/bin/bash
# Backup database SQLite + retensi 14 hari. Lihat docs/termux-deployment-guide.md
# langkah 7. Jalankan dari mana saja -- path dihitung relatif ke lokasi script ini.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATABASE="$APP_DIR/data/bot.db"
BACKUP_DIR="$APP_DIR/data/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

if [ ! -f "$DATABASE" ]; then
  echo "Database tidak ditemukan di $DATABASE, tidak ada yang di-backup."
  exit 0
fi

mkdir -p "$BACKUP_DIR"

sqlite3 "$DATABASE" ".backup '$BACKUP_DIR/bot-$TIMESTAMP.db'"
echo "Backup tersimpan: $BACKUP_DIR/bot-$TIMESTAMP.db"

find "$BACKUP_DIR" -type f -name "bot-*.db" -mtime +14 -delete
