#!/usr/bin/env bash
# Build COLMAP from source with CUDA for MX150 (Pascal) on Pop OS 24.
# Uses CUDA 12.x only: CUDA 13+ dropped support for compute_61 (Pascal).
# Usage:
#   bash scripts/build_colmap_cuda.sh
#
# After this script finishes, COLMAP will be installed to /usr/local.

set -e
COLMAP_DIR="$HOME/dev/colmap"
CUDA_ARCH="61"

echo "=========================================="
echo " COLMAP build from source (CUDA + MX150)"
echo "=========================================="

# ---- Step 1: Build dependencies (non-CUDA) ----
echo ""
echo "==> [1/6] Installing build dependencies..."
sudo apt update || true
sudo apt install -y --fix-missing \
  git cmake ninja-build build-essential \
  libboost-program-options-dev libboost-graph-dev libboost-system-dev \
  libeigen3-dev libmetis-dev \
  libgoogle-glog-dev libgtest-dev libgmock-dev libsqlite3-dev \
  libglew-dev qt6-base-dev libqt6opengl6-dev libqt6openglwidgets6 \
  libcgal-dev libceres-dev libsuitesparse-dev \
  libcurl4-openssl-dev libssl-dev \
  wget

# OpenImageIO (needs OpenCV include dir for its INTERFACE_INCLUDE_DIRECTORIES)
sudo apt install -y --fix-missing libopencv-dev || true
sudo apt install -y --fix-missing libopenimageio-dev openimageio-tools || \
  echo "WARNING: openimageio not installed, COLMAP will build without it"
# OpenImageIO may reference /usr/include/opencv4; ensure it exists
if [ ! -d /usr/include/opencv4 ]; then
  sudo mkdir -p /usr/include/opencv4
  echo "    Created /usr/include/opencv4 (OpenImageIO workaround)"
fi

# ---- Step 2: CUDA Toolkit (must be 12.x for MX150/Pascal; CUDA 13 dropped compute_61) ----
echo ""
echo "==> [2/6] CUDA toolkit (need 12.x for MX150; 13.x does not support Pascal)..."
CUDA_ROOT=""
if [ -d /usr/local/cuda-12.8 ]; then
  CUDA_ROOT="/usr/local/cuda-12.8"
  echo "    Using existing CUDA 12.8: $CUDA_ROOT"
elif [ -d /usr/local/cuda-12.6 ]; then
  CUDA_ROOT="/usr/local/cuda-12.6"
  echo "    Using existing CUDA 12.6: $CUDA_ROOT"
elif command -v nvcc &>/dev/null; then
  NVCC_VER=$(nvcc --version | sed -n 's/.*release \([0-9]*\)\.\([0-9]*\).*/\1\2/p')
  if [ -n "$NVCC_VER" ] && [ "$NVCC_VER" -lt 130 ]; then
    CUDA_ROOT="$(dirname "$(dirname "$(command -v nvcc)")")"
    echo "    Using existing nvcc (12.x): $CUDA_ROOT"
  fi
fi

if [ -z "$CUDA_ROOT" ]; then
  echo "    Installing CUDA 12.8 from NVIDIA (Pascal/MX150 compatible)..."
  CUDA_DEB="cuda-repo-ubuntu2404-12-8-local_12.8.0-570.86.10-1_amd64.deb"
  CUDA_DEB_URL="https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/${CUDA_DEB}"
  cd /tmp
  if [ ! -f "$CUDA_DEB" ]; then
    wget -q --show-progress "$CUDA_DEB_URL"
  fi
  sudo dpkg -i "$CUDA_DEB"
  sudo cp /var/cuda-repo-ubuntu2404-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/ 2>/dev/null || true
  sudo apt update
  sudo apt install -y cuda-toolkit-12-8
  cd -
  CUDA_ROOT="/usr/local/cuda-12.8"
  echo "    Installed: $CUDA_ROOT"
fi

export PATH="${CUDA_ROOT}/bin:$PATH"
export LD_LIBRARY_PATH="${CUDA_ROOT}/lib64:${LD_LIBRARY_PATH:-}"
export CUDA_TOOLKIT_ROOT_DIR="$CUDA_ROOT"
nvcc --version | grep release || true

# ---- Step 3: Clone COLMAP ----
echo ""
echo "==> [3/6] Cloning COLMAP..."
if [ -d "$COLMAP_DIR/.git" ]; then
  echo "    Directory $COLMAP_DIR exists, pulling latest..."
  cd "$COLMAP_DIR"
  git fetch --all
  git checkout main || git checkout master || true
  git pull || true
else
  rm -rf "$COLMAP_DIR"
  git clone https://github.com/colmap/colmap "$COLMAP_DIR"
  cd "$COLMAP_DIR"
fi

# ---- Step 4: Configure CMake ----
echo ""
echo "==> [4/6] Configuring CMake (CUDA arch=${CUDA_ARCH}, toolkit=$CUDA_ROOT)..."
rm -rf build
mkdir -p build && cd build
cmake .. -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DCUDA_ENABLED=ON \
  -DCMAKE_CUDA_COMPILER="${CUDA_ROOT}/bin/nvcc" \
  -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}" \
  -DTESTS_ENABLED=OFF

# ---- Step 5: Build ----
echo ""
echo "==> [5/6] Building COLMAP (this may take 10-30 minutes)..."
ninja

# ---- Step 6: Install ----
echo ""
echo "==> [6/6] Installing to /usr/local..."
sudo ninja install
sudo ldconfig

echo ""
echo "=========================================="
echo " Done!"
echo "=========================================="
echo ""
echo "Add this to your ~/.bashrc if not already there:"
echo "  export PATH=\"${CUDA_ROOT}/bin:\$PATH\""
echo "  export LD_LIBRARY_PATH=\"${CUDA_ROOT}/lib64:\$LD_LIBRARY_PATH\""
echo ""
echo "Verify:"
echo "  colmap -h"
echo "  nvcc --version"
echo "  nvidia-smi"
