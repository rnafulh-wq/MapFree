# tools/colmap/

This folder holds COLMAP-related tooling and patches.

## Files

### `colmap_bin_fix.patch`
Git patch that introduced configurable COLMAP binary resolution
(`MAPFREE_COLMAP_BIN` env var / `config colmap.colmap_bin`).
The patch is already applied to the codebase and is kept here for reference.

To apply manually (if needed on a clean branch):
```bash
git apply tools/colmap/colmap_bin_fix.patch
```

## COLMAP Installation

COLMAP is **not bundled** with MapFree. Install it separately:

- **Windows**: https://github.com/colmap/colmap/releases — or see `scripts/install_colmap_windows.md`
- **Linux**: `sudo apt install colmap` or build from source — see `scripts/build_colmap_mx150.sh`
- **Conda**: `conda install -c conda-forge colmap`

Set the binary path via environment variable or config:
```bash
export MAPFREE_COLMAP=/path/to/colmap          # Linux
set MAPFREE_COLMAP=C:\tools\COLMAP\COLMAP.bat  # Windows CMD
```
Or in `mapfree/core/config/default.yaml`:
```yaml
colmap:
  colmap_bin: /path/to/colmap
```
