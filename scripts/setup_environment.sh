#!/usr/bin/env bash
# MapFree — Setup development environment.
# Installs system dependencies, creates Python venv, installs MapFree.
# Usage: bash scripts/setup_environment.sh

set -e
cd "$(dirname "$0")/.."

echo "=========================================="
echo " MapFree — Setup Environment"
echo "=========================================="

echo ""
echo "==> [1/3] Installing system packages..."
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential

echo ""
echo "==> [2/3] Creating Python virtual environment..."
if [ -d venv ]; then
  echo "    venv already exists, skipping creation."
else
  python3 -m venv venv
fi
source venv/bin/activate

echo ""
echo "==> [3/3] Installing MapFree (editable)..."
pip install --upgrade pip
pip install -e .

echo ""
echo "=========================================="
echo " Done."
echo "=========================================="
echo ""
echo "Activate:  source venv/bin/activate"
echo "Verify:    mapfree run --help"
echo "Hardware:  bash scripts/detect_hardware.sh"
