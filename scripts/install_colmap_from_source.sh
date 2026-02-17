#!/usr/bin/env bash
# Install COLMAP from source only (no PPA). Pop!_OS 24 + MX150: CUDA ON (arch 61, Pascal).
# CUDA 13+ dropped support for compute_61; we use CUDA 12.x and install it if missing.
# Usage:
#   bash scripts/install_colmap_from_source.sh
# Optional: INSTALL_PREFIX=$HOME/.local  or  CUDA_ARCH=61  or  COLMAP_DIR=...
# To force CPU-only: CUDA_MX150=0 bash scripts/install_colmap_from_source.sh
set -e

COLMAP_DIR="${COLMAP_DIR:-$HOME/dev/colmap}"
INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local}"
# MX150 = Pascal = compute 6.1 → arch 61 (wajib CUDA 12.x; 13.x tidak support)
CUDA_ARCH="${CUDA_ARCH:-61}"
CUDA_MX150="${CUDA_MX150:-1}"

echo "=========================================="
echo " COLMAP — build from source (no PPA)"
echo "  Pop OS 24 + MX150 → CUDA ON (arch 61)"
echo "=========================================="
echo "  COLMAP_DIR=$COLMAP_DIR"
echo "  INSTALL_PREFIX=$INSTALL_PREFIX"
echo "  CUDA_ARCH=$CUDA_ARCH  CUDA_MX150=$CUDA_MX150"
echo ""

# ---- Step 1: Build dependencies ----
echo "==> [1/6] Installing build dependencies (sudo)..."
sudo apt update
sudo apt install -y --fix-missing \
  git cmake ninja-build build-essential \
  libboost-program-options-dev libboost-graph-dev libboost-system-dev \
  libeigen3-dev libmetis-dev \
  libgoogle-glog-dev libgtest-dev libgmock-dev libsqlite3-dev \
  libglew-dev qt6-base-dev libqt6opengl6-dev libqt6openglwidgets6 \
  libcgal-dev libceres-dev libsuitesparse-dev \
  libcurl4-openssl-dev libssl-dev \
  wget

sudo apt install -y --fix-missing libopencv-dev 2>/dev/null || true
sudo apt install -y --fix-missing libopenimageio-dev openimageio-tools 2>/dev/null || \
  echo "    (OpenImageIO optional, continuing without)"

if [ ! -d /usr/include/opencv4 ]; then
  sudo mkdir -p /usr/include/opencv4
fi

# ---- Step 2: CUDA 12.x for MX150 (Pascal); install if missing ----
echo ""
echo "==> [2/6] CUDA for MX150 (Pascal, arch 61) — CUDA 12.x required..."
CUDA_ROOT=""
CUDA_ENABLED="OFF"

if [ "$CUDA_MX150" = "1" ]; then
  for cuda in /usr/local/cuda-12.8 /usr/local/cuda-12.6 /usr/local/cuda-12; do
    if [ -d "$cuda" ] && [ -x "$cuda/bin/nvcc" ]; then
      CUDA_ROOT="$cuda"
      break
    fi
  done
  if [ -z "$CUDA_ROOT" ] && command -v nvcc &>/dev/null; then
    NVCC_VER=$(nvcc --version 2>/dev/null | sed -n 's/.*release \([0-9]*\)\.\([0-9]*\).*/\1\2/p')
    if [ -n "$NVCC_VER" ] && [ "$NVCC_VER" -lt 130 ]; then
      CUDA_ROOT="$(dirname "$(dirname "$(command -v nvcc)")")"
    fi
  fi

  if [ -z "$CUDA_ROOT" ]; then
    echo "    CUDA 12.x not found — installing CUDA 12.8 (compatible with MX150/Pascal)..."
    CUDA_DEB="cuda-repo-ubuntu2404-12-8-local_12.8.0-570.86.10-1_amd64.deb"
    CUDA_DEB_URL="https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/${CUDA_DEB}"
    cd /tmp
    if [ ! -f "$CUDA_DEB" ]; then
      wget -q --show-progress "$CUDA_DEB_URL" || { echo "ERROR: wget failed. Install CUDA 12.x manually."; exit 1; }
    fi
    sudo dpkg -i "$CUDA_DEB"
    sudo cp /var/cuda-repo-ubuntu2404-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/ 2>/dev/null || true
    sudo apt update
    sudo apt install -y cuda-toolkit-12-8
    cd - >/dev/null
    CUDA_ROOT="/usr/local/cuda-12.8"
    echo "    Installed: $CUDA_ROOT"
  fi

  if [ -n "$CUDA_ROOT" ]; then
    export PATH="${CUDA_ROOT}/bin:$PATH"
    export LD_LIBRARY_PATH="${CUDA_ROOT}/lib64:${LD_LIBRARY_PATH:-}"
    export CUDA_TOOLKIT_ROOT_DIR="$CUDA_ROOT"
    CUDA_ENABLED="ON"
    echo "    Using CUDA: $CUDA_ROOT (arch=$CUDA_ARCH, MX150/Pascal)"
    nvcc --version | grep release || true
  fi
fi

if [ "$CUDA_ENABLED" != "ON" ]; then
  echo "    Building without GPU (CPU only). Set CUDA_MX150=1 and install CUDA 12.x for MX150."
fi

# ---- Step 3: Clone COLMAP ----
echo ""
echo "==> [3/6] Cloning/updating COLMAP..."
if [ -d "$COLMAP_DIR/.git" ]; then
  cd "$COLMAP_DIR"
  git fetch --all
  git checkout main 2>/dev/null || git checkout master
  git pull --rebase || true
else
  mkdir -p "$(dirname "$COLMAP_DIR")"
  git clone https://github.com/colmap/colmap.git "$COLMAP_DIR"
  cd "$COLMAP_DIR"
fi

# ---- Step 4: Configure ----
echo ""
echo "==> [4/6] Configuring CMake (CUDA=$CUDA_ENABLED)..."
rm -rf build
mkdir -p build && cd build

CMAKE_EXTRA=()
if [ "$CUDA_ENABLED" = "ON" ]; then
  CMAKE_EXTRA+=(
    -DCUDA_ENABLED=ON
    -DCMAKE_CUDA_COMPILER="${CUDA_ROOT}/bin/nvcc"
    -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}"
  )
else
  CMAKE_EXTRA+=(-DCUDA_ENABLED=OFF)
fi

cmake .. -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
  -DTESTS_ENABLED=OFF \
  "${CMAKE_EXTRA[@]}"

# ---- Step 5: Build ----
echo ""
echo "==> [5/6] Building (10–30 min)..."
ninja -j$(nproc)

# ---- Step 6: Install ----
echo ""
echo "==> [6/6] Installing to $INSTALL_PREFIX..."
if [[ "$INSTALL_PREFIX" == /usr/* ]]; then
  sudo ninja install
  sudo ldconfig
else
  ninja install
  echo "    Add to PATH: export PATH=\"$INSTALL_PREFIX/bin:\$PATH\""
fi

echo ""
echo "=========================================="
echo " Done. Verify: colmap -h"
echo "=========================================="
if [ -n "$CUDA_ROOT" ]; then
  echo "CUDA: export PATH=\"${CUDA_ROOT}/bin:\$PATH\""
  echo "      export LD_LIBRARY_PATH=\"${CUDA_ROOT}/lib64:\$LD_LIBRARY_PATH\""
fi
