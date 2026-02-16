#!/usr/bin/env bash
# MapFree — Pre-build hardware check.
# Verifies GPU driver, CUDA compiler, system RAM, and COLMAP.
#
# NOTE: This is for quick pre-build validation ONLY.
#       Runtime detection is ALWAYS done by Python (mapfree/core/hardware.py).
#       Do NOT duplicate detection logic here.
# Usage: bash scripts/detect_hardware.sh

set -e

echo "=========================================="
echo " MapFree — Hardware Check (pre-build)"
echo "=========================================="

echo ""
echo "--- GPU ---"
if command -v nvidia-smi &>/dev/null; then
  echo "[OK] nvidia-smi found"
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
  echo "[WARN] nvidia-smi not found — GPU acceleration unavailable"
fi

echo ""
echo "--- CUDA Compiler ---"
if command -v nvcc &>/dev/null; then
  echo "[OK] nvcc found"
  nvcc --version | grep release
else
  echo "[INFO] nvcc not found — needed only to build COLMAP from source"
fi

echo ""
echo "--- System RAM ---"
if [ -f /proc/meminfo ]; then
  RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
  RAM_GB=$(echo "scale=1; $RAM_KB / 1048576" | bc)
  echo "[OK] System RAM: ${RAM_GB} GB"
else
  echo "[INFO] Cannot read /proc/meminfo"
fi

echo ""
echo "--- COLMAP ---"
if command -v colmap &>/dev/null; then
  echo "[OK] colmap found"
else
  echo "[WARN] colmap not found — run: bash scripts/build_engine.sh"
fi

echo ""
echo "=== For runtime detection, always use Python: ==="
echo "  python -c \"from mapfree.core import hardware; print('VRAM:', hardware.detect_gpu_vram(), 'MB')\""
