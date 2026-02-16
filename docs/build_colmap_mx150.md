# Build COLMAP for MX150

CUDA 11.5 is incompatible with GCC 11. The script uses **GCC 10 as host compiler only** (no CUDA upgrade, no driver change, no GCC 11 uninstall). It cleans the build directory and builds with:

- `CC=gcc-10` `CXX=g++-10`
- `-DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-10`
- Requires **libopenblas-dev** (installed by script when run with sudo).

**Run:** `./scripts/build_colmap_mx150.sh`

Options: `--no-install`, `--test-only /path/to/image.jpg`
