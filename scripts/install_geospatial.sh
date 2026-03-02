#!/usr/bin/env bash
# Install PDAL and GDAL for MapFree geospatial stages (DTM, DSM, orthophoto).
# Required commands: pdal, gdalinfo, gdal_grid, gdal_translate, gdalwarp (provided by gdal-bin).

set -e

echo "Installing geospatial dependencies for MapFree (PDAL, GDAL)..."

if command -v apt-get &>/dev/null; then
    sudo apt-get update
    sudo apt-get install -y pdal gdal-bin
    echo "Done. Verify with: pdal --version && gdalinfo --version"
elif command -v dnf &>/dev/null; then
    sudo dnf install -y pdal gdal
    echo "Done. Verify with: pdal --version && gdalinfo --version"
elif command -v brew &>/dev/null; then
    brew install pdal gdal
    echo "Done. Verify with: pdal --version && gdalinfo --version"
else
    echo "No supported package manager (apt-get, dnf, brew). Install manually:"
    echo "  Ubuntu/Debian: sudo apt install pdal gdal-bin"
    echo "  Fedora: sudo dnf install pdal gdal"
    echo "  macOS: brew install pdal gdal"
    echo "  Conda: conda install -c conda-forge pdal gdal"
    exit 1
fi

# Quick check
for cmd in pdal gdalinfo gdal_grid gdal_translate gdalwarp; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Warning: $cmd not found on PATH after install."
    fi
done
