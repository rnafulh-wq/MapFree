#!/usr/bin/env bash
# MapFree pipeline entry script. Env: IMAGE_FOLDER, OUTPUT_FOLDER, QUALITY (high|medium|low).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_FOLDER="${IMAGE_FOLDER:-$1}"
OUTPUT_FOLDER="${OUTPUT_FOLDER:-$2}"
QUALITY="${QUALITY:-medium}"
if [ -z "$IMAGE_FOLDER" ] || [ -z "$OUTPUT_FOLDER" ]; then
  echo "Usage: IMAGE_FOLDER=... OUTPUT_FOLDER=... [QUALITY=high|medium|low] $0"
  exit 1
fi
cd "$PROJECT_ROOT"
exec python3 -m mapfree.cli run "$IMAGE_FOLDER" --output "$OUTPUT_FOLDER" --quality "$QUALITY"
