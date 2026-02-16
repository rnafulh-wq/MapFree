#!/usr/bin/env bash
# Run this in your terminal to install all dependencies (SETUP_POPOS.md).
# Usage: bash scripts/setup_popos.sh

set -e
cd "$(dirname "$0")/.."

echo "==> Installing system packages (sudo required)..."
sudo apt update
sudo apt install -y python3.12-venv
sudo add-apt-repository -y ppa:savoury1/colmap
sudo apt update
sudo apt install -y colmap

echo "==> Creating Python venv and installing MapFree..."
python3 -m venv venv
source venv/bin/activate
pip install -e .

echo ""
echo "Done. Verify with:"
echo "  source venv/bin/activate"
echo "  colmap -h"
echo "  nvidia-smi"
echo "  mapfree run --help"
