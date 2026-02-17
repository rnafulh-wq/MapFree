#!/usr/bin/env bash
# 1) Hapus colmap dari /usr/local/bin
# 2) Install COLMAP dari source (CUDA ON untuk MX150) ke dalam venv proyek — tidak bentrok dengan sistem.
# Jalankan dari root repo: bash scripts/install_colmap_in_venv.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/venv"

echo "=========================================="
echo " COLMAP → install di venv (CUDA ON)"
echo "  Repo: $REPO_ROOT"
echo "  Venv: $VENV_DIR"
echo "=========================================="

# ---- 1) Hapus colmap sistem ----
echo ""
echo "==> [1/4] Menghapus colmap dari /usr/local/bin..."
if [ -f /usr/local/bin/colmap ] || [ -f /usr/local/bin/colmap.bin ]; then
  if sudo rm -f /usr/local/bin/colmap /usr/local/bin/colmap.bin 2>/dev/null; then
    echo "    Dihapus: /usr/local/bin/colmap (dan .bin)"
  else
    echo "    Sudo gagal — hapus manual lalu jalankan ulang:"
    echo "    sudo rm -f /usr/local/bin/colmap /usr/local/bin/colmap.bin"
  fi
else
  echo "    Tidak ada colmap di /usr/local/bin, skip."
fi

# ---- 2) Buat venv bila belum ada ----
echo ""
echo "==> [2/4] Menyiapkan venv..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  echo "    Venv dibuat: $VENV_DIR"
else
  echo "    Venv sudah ada: $VENV_DIR"
fi

# ---- 3) Build & install COLMAP ke venv (CUDA ON) ----
echo ""
echo "==> [3/4] Build COLMAP dari source (CUDA ON, arch 61) → install ke venv..."
export INSTALL_PREFIX="$VENV_DIR"
export CUDA_MX150=1
export CUDA_ARCH=61
"$SCRIPT_DIR/install_colmap_from_source.sh"

# ---- 4) Pastikan PATH venv dipakai ----
echo ""
echo "==> [4/4] Selesai."
echo "    Colmap binary: $VENV_DIR/bin/colmap"
echo ""
echo "Pakai COLMAP di venv:"
echo "  source $VENV_DIR/bin/activate"
echo "  colmap -h"
echo "  mapfree run <images> -o <output>   # mapfree akan memakai colmap dari venv"
echo ""
