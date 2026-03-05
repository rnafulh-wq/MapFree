#!/usr/bin/env bash
# MapFree Engine Linux Installer v1.1
# Interactive shell installer: detect hardware, install COLMAP, optional MapFree + desktop entry.
# Run from repo root (or set MAPFREE_APPIMAGE to path of AppImage): ./scripts/installer/install_linux.sh

set -e

echo "╔══════════════════════════════════════╗"
echo "║     MapFree Engine Installer v1.1    ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Detect distro (Ubuntu/Debian/Arch/Fedora)
detect_distro() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    source /etc/os-release
    case "${ID:-}" in
      ubuntu|debian|pop|linuxmint)
        echo "debian"
        ;;
      arch|manjaro)
        echo "arch"
        ;;
      fedora|rhel|centos)
        echo "fedora"
        ;;
      *)
        echo "unknown"
        ;;
    esac
  else
    echo "unknown"
  fi
}

# Detect GPU for COLMAP variant hint
detect_gpu() {
  if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    echo "nvidia"
  elif lspci 2>/dev/null | grep -qi "vga.*amd\|amd.*graphics"; then
    echo "amd"
  elif lspci 2>/dev/null | grep -qi "vga.*intel"; then
    echo "intel"
  else
    echo "cpu"
  fi
}

DISTRO=$(detect_distro)
GPU=$(detect_gpu)
RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo "?")

echo "Hardware terdeteksi:"
echo "  Distro: $DISTRO"
echo "  GPU:    $GPU"
echo "  RAM:    ${RAM_GB}GB"
echo ""

echo "Akan diinstall:"
echo "  [✓] MapFree Engine (ke ~/.local/bin atau dari AppImage)"
echo "  [✓] COLMAP ($([ "$GPU" = "nvidia" ] && echo "paket sistem (CUDA bila tersedia)" || echo "paket sistem"))"
echo ""
read -p "Lanjutkan? [Y/n] " confirm
if [[ "${confirm,,}" =~ ^n ]]; then
  echo "Dibatalkan."
  exit 0
fi

# Install COLMAP via package manager
install_colmap() {
  case "$DISTRO" in
    debian)
      if command -v sudo &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y colmap
      else
        echo "Perlu sudo untuk install COLMAP. Jalankan: apt-get install -y colmap"
      fi
      ;;
    fedora)
      if command -v sudo &>/dev/null; then
        sudo dnf install -y colmap
      else
        echo "Perlu sudo untuk install COLMAP. Jalankan: dnf install -y colmap"
      fi
      ;;
    arch)
      if command -v sudo &>/dev/null; then
        sudo pacman -Sy --noconfirm colmap
      else
        echo "Perlu sudo untuk install COLMAP. Jalankan: pacman -Sy colmap"
      fi
      ;;
    *)
      echo "Distro tidak dikenali. Install COLMAP manual: https://colmap.github.io/"
      ;;
  esac
}

install_colmap

# Install MapFree binary / AppImage to ~/.local/bin and create desktop entry
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_BIN="${HOME}/.local/bin"
mkdir -p "$LOCAL_BIN"

if [[ -n "${MAPFREE_APPIMAGE:-}" && -f "${MAPFREE_APPIMAGE}" ]]; then
  cp "$MAPFREE_APPIMAGE" "$LOCAL_BIN/mapfree.AppImage"
  chmod +x "$LOCAL_BIN/mapfree.AppImage"
  echo "MapFree AppImage disalin ke $LOCAL_BIN/mapfree.AppImage"
  if [[ -f "$SCRIPT_DIR/create_desktop_entry.sh" ]]; then
    bash "$SCRIPT_DIR/create_desktop_entry.sh" "$LOCAL_BIN/mapfree.AppImage"
  fi
elif [[ -f "$REPO_ROOT/dist/MapFree-x86_64.AppImage" ]]; then
  cp "$REPO_ROOT/dist/MapFree-x86_64.AppImage" "$LOCAL_BIN/mapfree.AppImage"
  chmod +x "$LOCAL_BIN/mapfree.AppImage"
  echo "MapFree AppImage disalin ke $LOCAL_BIN/mapfree.AppImage"
  if [[ -f "$SCRIPT_DIR/create_desktop_entry.sh" ]]; then
    bash "$SCRIPT_DIR/create_desktop_entry.sh" "$LOCAL_BIN/mapfree.AppImage"
  fi
else
  echo "Tidak ada AppImage ditemukan. Untuk first-run setup (deteksi hardware, download deps),"
  echo "jalankan MapFree AppImage sekali; wizard akan muncul (lihat TASK 1.6)."
  echo "Pastikan ~/.local/bin ada di PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "Selesai. Jalankan MapFree dari launcher atau: $LOCAL_BIN/mapfree.AppImage"
