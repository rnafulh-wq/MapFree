#!/usr/bin/env bash
# MapFree — Build COLMAP from source with CUDA.
# Detects installed CUDA version and builds accordingly.
#
# For MX150 (Pascal): needs CUDA 12.x (CUDA 13 dropped compute_61).
# Usage: bash scripts/build_engine.sh [--cuda-arch 61]

set -e

COLMAP_DIR="$HOME/dev/colmap"
CUDA_ARCH="${1:-61}"   # default: Pascal (MX150)

echo "=========================================="
echo " MapFree — Build Engine (COLMAP + CUDA)"
echo "=========================================="

# --- Find CUDA 12.x ---
echo ""
echo "==> [1/5] Locating CUDA toolkit (need 12.x for Pascal)..."
CUDA_ROOT=""
for candidate in /usr/local/cuda-12.8 /usr/local/cuda-12.6 /usr/local/cuda-12.4 /usr/local/cuda-12; do
  if [ -x "${candidate}/bin/nvcc" ]; then
    CUDA_ROOT="$candidate"
    break
  fi
done

if [ -z "$CUDA_ROOT" ]; then
  echo "    No CUDA 12.x found. Installing CUDA 12.8..."
  CUDA_DEB="cuda-repo-ubuntu2404-12-8-local_12.8.0-570.86.10-1_amd64.deb"
  CUDA_URL="https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/${CUDA_DEB}"
  cd /tmp
  [ -f "$CUDA_DEB" ] || wget -q --show-progress "$CUDA_URL"
  sudo dpkg -i "$CUDA_DEB"
  sudo cp /var/cuda-repo-ubuntu2404-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/ 2>/dev/null || true
  sudo apt update
  sudo apt install -y cuda-toolkit-12-8
  cd -
  CUDA_ROOT="/usr/local/cuda-12.8"
fi
export PATH="${CUDA_ROOT}/bin:$PATH"
export LD_LIBRARY_PATH="${CUDA_ROOT}/lib64:${LD_LIBRARY_PATH:-}"
echo "    Using: $CUDA_ROOT ($(nvcc --version | grep release))"

# --- Install build deps ---
echo ""
echo "==> [2/5] Installing build dependencies..."
sudo apt update || true
sudo apt install -y --fix-missing \
  git cmake ninja-build build-essential \
  libboost-program-options-dev libboost-graph-dev libboost-system-dev \
  libeigen3-dev libmetis-dev \
  libgoogle-glog-dev libgtest-dev libgmock-dev libsqlite3-dev \
  libglew-dev qt6-base-dev libqt6opengl6-dev libqt6openglwidgets6 \
  libcgal-dev libceres-dev libsuitesparse-dev \
  libcurl4-openssl-dev libssl-dev wget
sudo apt install -y --fix-missing libopencv-dev libopenimageio-dev openimageio-tools || true
[ -d /usr/include/opencv4 ] || sudo mkdir -p /usr/include/opencv4

# --- Clone ---
echo ""
echo "==> [3/5] Cloning COLMAP..."
if [ -d "$COLMAP_DIR/.git" ]; then
  echo "    $COLMAP_DIR exists, pulling..."
  cd "$COLMAP_DIR" && git pull || true
else
  rm -rf "$COLMAP_DIR"
  git clone https://github.com/colmap/colmap "$COLMAP_DIR"
  cd "$COLMAP_DIR"
fi

# --- Configure + Build ---
echo ""
echo "==> [4/5] Configuring CMake (CUDA arch=${CUDA_ARCH})..."
rm -rf build && mkdir -p build && cd build
cmake .. -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DCUDA_ENABLED=ON \
  -DCMAKE_CUDA_COMPILER="${CUDA_ROOT}/bin/nvcc" \
  -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}" \
  -DTESTS_ENABLED=OFF

echo ""
echo "==> [5/5] Building (this may take 10-30 minutes)..."
ninja

echo ""
echo "==> Installing to /usr/local..."
sudo ninja install
sudo ldconfig

echo ""
echo "=========================================="
echo " Done!"
echo "=========================================="
echo ""
echo "Add to ~/.bashrc:"
echo "  export PATH=\"${CUDA_ROOT}/bin:\$PATH\""
echo ""
echo "Verify:"
echo "  colmap -h"
echo "  nvcc --version"
