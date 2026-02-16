#!/bin/bash
# Backup MapFree project untuk migrasi ke Pop OS 24 LTS Nvidia
# Exclude: venv, __pycache__, generated data

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${1:-$HOME/mapfree_backup}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${BACKUP_DIR}/mapfree_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_ROOT"

echo "=== MapFree Backup ==="
echo "Project: $PROJECT_ROOT"
echo "Output:  $ARCHIVE"
echo ""

tar --exclude='venv' \
    --exclude='.venv' \
    --exclude='env' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git' \
    --exclude='projects' \
    --exclude='logs' \
    --exclude='*.db' \
    --exclude='*.log' \
    --exclude='test_images' \
    --exclude='dense' \
    --exclude='.done_*' \
    -czvf "$ARCHIVE" .

echo ""
echo "Backup selesai: $ARCHIVE"
echo "Ukuran: $(du -h "$ARCHIVE" | cut -f1)"
echo ""
echo "Untuk restore di Pop OS:"
echo "  1. Copy file ini ke Pop OS"
echo "  2. tar -xzvf mapfree_*.tar.gz -C /path/to/dest"
echo "  3. Ikuti SETUP_POPOS.md"
