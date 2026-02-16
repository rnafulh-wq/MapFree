#!/usr/bin/env bash
# Build COLMAP from source for MX150 (Pascal, CUDA arch 61).
# CUDA 11.5 is incompatible with GCC 11; use GCC 10 as host compiler only (no CUDA/driver change).
# Steps: 1) Clean old COLMAP, 2) Install GCC 10 + libopenblas-dev + deps, 3) Clone, 4) Clean build + cmake+ninja, 5) Test GPU SIFT.
#
# Usage:
#   ./scripts/build_colmap_mx150.sh [--no-install] [--test-only PATH_TO_IMAGE]
set -e

COLMAP_SRC_DIR="${COLMAP_SRC_DIR:-$HOME/colmap_src}"
COLMAP_BUILD_DIR="${COLMAP_BUILD_DIR:-$HOME/colmap_build}"
INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local}"
NO_INSTALL=""
TEST_ONLY_IMG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-install) NO_INSTALL=1; shift ;;
    --test-only)  TEST_ONLY_IMG="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

test_gpu_sift() {
  local img="${1:-}"
  [[ -z "$img" ]] && { echo "Usage: $0 --test-only /path/to/image.jpg"; exit 1; }
  [[ ! -f "$img" ]] && { echo "Image not found: $img"; exit 1; }
  echo "=== Testing GPU SIFT (single image) ==="
  local tmpdb=$(mktemp -u).db
  local tmpdir=$(mktemp -d)
  cp "$img" "$tmpdir/"
  colmap feature_extractor --database_path "$tmpdb" --image_path "$tmpdir" \
    --ImageReader.camera_model OPENCV --ImageReader.single_camera 1 \
    --SiftExtraction.use_gpu 1 --SiftExtraction.gpu_index 0 \
    --SiftExtraction.max_image_size 2000 --SiftExtraction.max_num_features 4096
  echo "GPU SIFT test OK."
  rm -f "$tmpdb"; rm -rf "$tmpdir"
  exit 0
}

[[ -n "$TEST_ONLY_IMG" ]] && test_gpu_sift "$TEST_ONLY_IMG"

# Skip steps that need sudo when running non-interactively (e.g. no password)
SKIP_SUDO=""
if ! sudo -n true 2>/dev/null; then
  SKIP_SUDO=1
  echo "Sudo not available (no password). Skipping [1] clean and [2] install deps."
  echo "Run manually with sudo: apt install gcc-10 g++-10 cmake ninja-build libopenblas-dev + COLMAP deps."
fi

if [[ -z "$SKIP_SUDO" ]]; then
  echo "=== [1/5] Cleaning old COLMAP ==="
  sudo apt-get remove -y colmap 2>/dev/null || true
  [[ -f "$INSTALL_PREFIX/bin/colmap" ]] && sudo rm -f "$INSTALL_PREFIX/bin/colmap" "$INSTALL_PREFIX/bin/colmap.bin" 2>/dev/null || true

  echo "=== [2/5] Installing GCC 10 and dependencies ==="
  sudo apt-get update
  sudo apt-get install -y gcc-10 g++-10 git cmake ninja-build build-essential \
    libopenblas-dev \
    libboost-program-options-dev libboost-graph-dev libboost-system-dev \
    libeigen3-dev libfreeimage-dev libmetis-dev libgoogle-glog-dev \
    libgtest-dev libgmock-dev libsqlite3-dev libglew-dev \
    libqt6base6-dev libqt6opengl6-dev libqt6openglwidgets6 \
    libcgal-dev libceres-dev libcurl4-openssl-dev libssl-dev
  sudo apt-get install -y nvidia-cuda-toolkit nvidia-cuda-toolkit-gcc 2>/dev/null || true
else
  echo "=== [1/5] Skipped (need sudo) ==="
  echo "=== [2/5] Skipped (need sudo) ==="
  command -v gcc-10 >/dev/null 2>&1 || { echo "Error: gcc-10 not found. Install with: sudo apt install gcc-10 g++-10"; exit 1; }
  command -v pkg-config >/dev/null 2>&1 && pkg-config --exists openblas 2>/dev/null || true
  if [ ! -f /usr/lib/x86_64-linux-gnu/libopenblas.so ] && [ ! -f /usr/lib/libopenblas.so ]; then
    echo "Warning: libopenblas not found. Build may fail. Install: sudo apt install libopenblas-dev"
  fi
fi

echo "=== [3/5] Clone fresh COLMAP ==="
if [[ -d "$COLMAP_SRC_DIR" ]]; then
  (cd "$COLMAP_SRC_DIR" && git fetch origin && git checkout main && git pull --rebase)
else
  git clone https://github.com/colmap/colmap.git "$COLMAP_SRC_DIR"
fi

echo "=== [4/5] Build with GCC 10 (CUDA 11.5 host compiler), arch 61 (Pascal/MX150) ==="
# Clean build directory for reproducible CUDA+GCC-10 build (do not use GCC 11 with CUDA 11.5)
rm -rf "$COLMAP_BUILD_DIR"
mkdir -p "$COLMAP_BUILD_DIR" && cd "$COLMAP_BUILD_DIR"
export CC=/usr/bin/gcc-10 CXX=/usr/bin/g++-10
BLAS_CMAKE=""
for blas in /usr/lib/x86_64-linux-gnu/libopenblas.so /usr/lib/libopenblas.so; do
  [ -f "$blas" ] && BLAS_CMAKE="-DBLAS_LIBRARIES=$blas -DLAPACK_LIBRARIES=$blas" && break
done
cmake "$COLMAP_SRC_DIR" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
  -DCMAKE_CUDA_ARCHITECTURES=61 \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-10 \
  -DBLA_VENDOR=OpenBLAS $BLAS_CMAKE
ninja -j$(nproc)

if [[ -z "$NO_INSTALL" ]] && [[ -z "$SKIP_SUDO" ]]; then
  sudo ninja install
  echo "Done. Run: colmap -h"
elif [[ -z "$NO_INSTALL" ]] && [[ -n "$SKIP_SUDO" ]]; then
  echo "Skipping install (no sudo). Run: cd $COLMAP_BUILD_DIR && sudo ninja install"
else
  echo "Skipping install. Binary: $COLMAP_BUILD_DIR/src/colmap/colmap"
fi

echo "=== [5/5] Test GPU SIFT: $0 --test-only /path/to/image.jpg"
