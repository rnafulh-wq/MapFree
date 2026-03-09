#!/usr/bin/env bash
# Verify PDAL and GDAL are installed and on PATH.
# Run from project root: ./scripts/check_geospatial.sh

set -e

echo "=== PATH ==="
echo "$PATH"
echo ""

echo "=== Which (must all exist) ==="
for cmd in pdal gdalinfo gdal_grid gdal_translate gdalwarp; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "  $cmd: $(command -v "$cmd")"
  else
    echo "  $cmd: NOT FOUND"
    exit 1
  fi
done
echo ""

echo "=== Versions ==="
pdal --version 2>/dev/null || true
gdalinfo --version 2>/dev/null || true
echo ""

echo "=== MapFree dependency check ==="
cd "$(dirname "$0")/.."
python -c "
from mapfree.utils.dependency_check import check_geospatial_dependencies
check_geospatial_dependencies()
print('PDAL & GDAL OK — geospatial stages can run.')
"
