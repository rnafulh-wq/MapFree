#!/bin/bash
# Backup MapFree project untuk migrasi ke Pop OS 24 LTS Nvidia
# Usage: ./scripts/backup_mapfree.sh [output_dir]
#        ./scripts/backup_mapfree.sh [output_dir] code-only  # exclude images (lebih kecil)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${1:-$HOME/mapfree_backup}"
CODE_ONLY="${2:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${BACKUP_DIR}/mapfree_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_ROOT"

echo "=== MapFree Backup ==="
echo "Project: $PROJECT_ROOT"
echo "Output:  $ARCHIVE"
[ -n "$CODE_ONLY" ] && echo "Mode:    code-only (no images)"
echo ""

EXCLUDES=(--exclude='venv' \
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
    --exclude='project_output' \
    --exclude='sparse')

[ -n "$CODE_ONLY" ] && EXCLUDES+=(--exclude='images')

tar "${EXCLUDES[@]}" -czvf "$ARCHIVE" .

echo ""
echo "Backup selesai: $ARCHIVE"
echo "Ukuran: $(du -h "$ARCHIVE" | cut -f1)"
echo ""
echo "Untuk restore di Pop OS:"
echo "  1. Copy file ini ke Pop OS"
echo "  2. tar -xzvf mapfree_*.tar.gz -C /path/to/dest"
echo "  3. Ikuti SETUP_POPOS.md"
