<p align="center">
  <img src="assets/MapFree_logo_desktop.png" width="600"/>
</p>

<p align="center">
  <a href="https://www.gnu.org/licenses/agpl-3.0">
    <img src="https://img.shields.io/badge/License-AGPL_v3-blue.svg" alt="License: AGPL v3"/>
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"/>
  </a>
  <a href="https://github.com/rnafulh-wq/MapFree/actions">
    <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha"/>
  </a>
</p>

# MapFree Engine

**Native Desktop Photogrammetry Engine for Drone Mapping**

MapFree is an open-source desktop application that transforms drone photos into
georeferenced 3D models, point clouds, Digital Surface Models (DSM), Digital
Terrain Models (DTM), and orthophotos — using COLMAP and OpenMVS under the hood,
with a user-friendly GUI built on PySide6.

---

## Features

- 🗺️ **GPS-aware pipeline** — automatically detects GPS from DJI/drone photos and
  uses spatial matching for best reconstruction accuracy
- 🏗️ **Full photogrammetry pipeline** — Sparse → Dense → DSM → DTM → Orthophoto
- 🖥️ **Native desktop GUI** — project panel, live console, progress tracking,
  OSM basemap with photo location overlay
- ⚡ **GPU accelerated** — CUDA support via COLMAP; automatic CPU fallback
- 📦 **Single-environment install** — all dependencies in one conda environment
- 🔧 **Smart matcher selection** — auto-selects spatial/sequential/exhaustive
  matcher based on GPS availability and dataset size
- 📁 **Organized output** — Metashape-style folder structure
  (`01_sparse/`, `02_dense/`, `03_mesh/`, `04_geospatial/`, `05_exports/`)

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10 64-bit | Windows 11 64-bit |
| RAM | 8 GB | 16 GB |
| GPU | CPU-only mode | NVIDIA CUDA (2GB+ VRAM) |
| Storage | 10 GB (install) + project space | SSD, 50GB+ |
| Python | 3.11 (via conda) | 3.11 |

> **Note:** MapFree has been tested with up to 335 drone photos (DJI, 4000×3000px)
> on a machine with NVIDIA MX150 (2GB VRAM) and 12GB RAM.

---

## Installation (Windows)

### Prerequisites

1. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
2. Download [COLMAP 3.13+](https://github.com/colmap/colmap/releases) and add to PATH

### Install MapFree

```powershell
# 1. Clone repository
git clone https://github.com/rnafulh-wq/MapFree.git
cd MapFree

# 2. Create conda environment (includes GDAL, PDAL, PySide6)
conda env create -f environment.yml

# 3. Activate environment
conda activate mapfree_engine

# 4. Install MapFree
pip install -e .

# 5. Verify
python -c "import mapfree; print('MapFree OK')"
gdalinfo --version
pdal --version
```

### Run

```powershell
conda activate mapfree_engine
python -m mapfree
```

---

## Quick Start

1. **Import photos** — click **Add Photos** or **Add Folder** to import drone photos
2. **Set output folder** — click **Select folder...**
3. **Choose quality** — Medium is recommended for most datasets
4. **Matching Method** — leave as **Auto (Recommended)**; MapFree will use spatial
   matching automatically if your photos have GPS
5. **Click Run** — pipeline runs in background; progress shown per stage

### Output

```
your_project/
├── 01_sparse/          ← Sparse point cloud + camera positions
├── 02_dense/           ← Dense point cloud (fused.ply)
├── 03_mesh/            ← 3D mesh (if enabled)
├── 04_geospatial/
│   ├── dense.las       ← Point cloud in LAS format
│   ├── classified.las  ← Ground-classified point cloud
│   ├── dsm.tif         ← Digital Surface Model (GeoTIFF)
│   ├── dtm.tif         ← Digital Terrain Model (GeoTIFF)
│   └── orthophoto.tif  ← Orthophoto (GeoTIFF)
├── 05_exports/         ← Exported formats
└── logs/
    └── mapfree.log     ← Full pipeline log
```

All GeoTIFF outputs are georeferenced (EPSG based on GPS coordinates of photos,
e.g. EPSG:32751 for UTM Zone 51S / Nusa Tenggara).

---

## Codebase Structure

```
MapFree/
├── mapfree/
│   ├── __main__.py         ← Entry point (python -m mapfree)
│   ├── app.py              ← GUI application startup
│   ├── core/               ← Pipeline, EventBus, context, chunking, validation
│   ├── engines/            ← COLMAP and OpenMVS engine implementations
│   ├── application/       ← Controller, project manager, state machine
│   ├── gui/                ← PySide6 main window, panels, dialogs, workers
│   ├── geospatial/         ← DSM/DTM/orthophoto generation (PDAL + GDAL)
│   ├── utils/              ← Logger, file_utils, process_utils, dependency_check
│   └── config/             ← Default YAML configs and load_config
├── tests/                  ← Unit and integration tests
├── scripts/                ← Windows installer and launcher scripts
├── docs/                   ← Documentation
├── environment.yml         ← Conda environment (mapfree_engine)
├── pyproject.toml
├── requirements.txt
├── LICENSE                 ← GNU AGPL v3
├── CONTRIBUTING.md
├── CHANGELOG.md
└── README.md
```

---

## Pipeline Overview

```
Photos (drone/UAV with GPS)
        │
        ▼
Feature Extraction     ← COLMAP: detect keypoints in each photo
        │
        ▼
Feature Matching       ← COLMAP: spatial matcher (GPS-based) by default
        │
        ▼
Sparse Reconstruction  ← COLMAP: Structure-from-Motion → cameras + sparse points
        │
        ▼
Dense Reconstruction   ← COLMAP/OpenMVS: Multi-View Stereo → dense point cloud
        │
        ▼
Geospatial Processing  ← PDAL + GDAL: LAS → DSM → DTM → Orthophoto (GeoTIFF)
        │
        ▼
Post-Processing        ← Merge, export, organize outputs
```

---

## Dependency Licenses

MapFree is licensed under **GNU AGPL v3** (required by OpenMVS dependency).

| Dependency | License | Role |
|------------|---------|------|
| [COLMAP](https://colmap.github.io/) | BSD 3-Clause | Sparse & dense reconstruction |
| [OpenMVS](https://github.com/cdcseacave/openMVS) | **AGPL v3** | Dense mesh & texturing |
| [GDAL](https://gdal.org/) | MIT/X | Raster geospatial processing |
| [PDAL](https://pdal.io/) | BSD | Point cloud processing |
| [PySide6](https://doc.qt.io/qtforpython/) | LGPL v3 | GUI framework |

---

## Troubleshooting

**COLMAP not found**
```powershell
# Verify COLMAP is on PATH
where.exe colmap
# If not found, add COLMAP to PATH or set MAPFREE_COLMAP_BIN env variable
```

**GPS not detected (0 dengan GPS)**
```powershell
# Ensure running from mapfree_engine, not base
conda activate mapfree_engine
python -m mapfree
```

**Geospatial stage skipped**
```powershell
# Install GDAL and PDAL in mapfree_engine
conda activate mapfree_engine
conda install -c conda-forge gdal pdal -y
gdalinfo --version  # verify
pdal --version      # verify
```

**Pipeline error — check log**
```powershell
Get-Content "your_project\logs\mapfree.log" | Select-Object -Last 50
```

---

## Roadmap

| Version | Target | Focus |
|---------|--------|-------|
| **v1.1.0** | Q1 2026 | Stable pipeline, Windows installer, GPS georeferencing |
| v1.2 | Q2 2026 | Core architecture refactor, project system, job system |
| v1.3 | Q3 2026 | Pipeline stage system, YAML config, resume from any stage |
| v1.4 | Q3 2026 | Structured logging, crash reports |
| v1.5 | Q4 2026 | GUI API Bridge, full responsive layout |
| v1.6 | Q1 2027 | Plugin system (custom engines, stages) |
| v1.7 | Q2 2027 | Performance for 500–5000 photos |

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup with conda
- Branch and commit conventions
- Testing guidelines (including real-world drone photo tests)
- Pull request process

---

## License

MapFree Engine is licensed under the
**GNU Affero General Public License v3.0 (AGPL v3)**.

This is required for compatibility with OpenMVS (AGPL v3).
See [LICENSE](LICENSE) for the full text.

---

## Acknowledgments

- [COLMAP](https://colmap.github.io/) — J.L. Schönberger, J.-M. Frahm (ETH Zurich)
- [OpenMVS](https://github.com/cdcseacave/openMVS) — cDc
- [GDAL](https://gdal.org/) — OSGeo
- [PDAL](https://pdal.io/) — PDAL Contributors

---

## Support

- **Bug reports**: [GitHub Issues](https://github.com/rnafulh-wq/MapFree/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rnafulh-wq/MapFree/discussions)

---

*MapFree Engine — Free tools for everyone to map the world.*
