# MapFree Engine

**Native Desktop Photogrammetry Engine**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/your-org/MapFree)

## Overview

MapFree is a native desktop photogrammetry engine built with PySide6 and a modular event-driven architecture. It orchestrates COLMAP and OpenMVS pipelines to reconstruct 3D models from image datasets.

The application does not implement SfM or MVS algorithms itself; it drives external binaries (COLMAP for structure-from-motion and dense reconstruction, OpenMVS for meshing and texturing) and manages project state, hardware-adaptive profiles, chunking, and resume behaviour.

## Key Features

- **Native desktop GUI** — PySide6-based interface with project panel, live console, progress tracking, and viewer placeholder.
- **Event-driven pipeline architecture** — Pipeline stages emit events via an in-process EventBus; GUI and CLI subscribe for progress and logs without blocking.
- **Modular engine system** — Sparse and dense backends are pluggable (COLMAP, OpenMVS); engine interface is abstracted for future extensions.
- **Live progress tracking** — Stage and progress updates flow from pipeline to UI through Qt signals; no polling.
- **Commercial-ready architecture** — Layered design (Core, Application, GUI), structured logging, and clear separation of orchestration from engines.
- **Extensible for custom SfM/MVS engines** — New engines can be added by implementing the engine contract and registering in the pipeline.

## Architecture

The codebase is organized in layers:

**Core → Application → GUI → Infrastructure**

- **Core** (`mapfree/core/`) — Pipeline orchestration, project context, EventBus, state persistence, validation, chunking, and hardware detection. No UI dependencies.
- **Application** (`mapfree/application/`) — MapFreeController runs the pipeline in a worker thread and subscribes to the context EventBus; project manager, license manager, and state machine stubs live here.
- **GUI** (`mapfree/gui/`) — PySide6 main window, QtController (adapts controller events to Qt signals), PipelineWorker (QThread), panels (project, console, progress, viewer), and dialogs. Connects to Application via signals only.
- **Infrastructure** — Engines (`mapfree/engines/`), config (`mapfree/config/`), and utils (logging, file helpers, process helpers).

Important components:

- **EventBus** — In-process, thread-safe pub/sub. Pipeline and engines emit events (e.g. `pipeline_started`, `progress_updated`, `engine_log`); controller and QtController subscribe and update state or emit Qt signals.
- **Controller** — Starts the pipeline in a background thread, attaches to the run’s EventBus, and exposes `run_project` / `stop_project` and optional callbacks. No direct engine calls from the controller.
- **Pipeline** — Coordinates prepare → sparse (feature extraction, matching, mapper, optional chunking/merge) → dense → post-process. Uses engine abstraction and context; emits progress and stage events via EventBus.
- **Engine abstraction** — Sparse/dense backends (e.g. COLMAP, OpenMVS) implement a common interface; pipeline invokes them via the wrapper and streams logs through the context EventBus.

## Installation

### Requirements

- Python 3.10+
- **Python dependencies** (installed automatically with MapFree): PySide6, NumPy, OpenCV, PyYAML, psutil, tqdm. Use `pip install -e .` or `pip install -r requirements.txt`.
- COLMAP installed and on PATH (or set `MAPFREE_COLMAP_BIN`)
- OpenMVS installed and on PATH if using dense mesh pipeline (optional; COLMAP dense is default)
- **PDAL and GDAL** — required only for geospatial stages (LAS conversion, DSM/DTM, orthophoto). Not bundled; must be installed on the system and on PATH.

### PDAL & GDAL (geospatial)

MapFree does not ship PDAL or GDAL. Install them and ensure they are on your PATH.

**Ubuntu / Debian (or use project script):**

```bash
./scripts/install_geospatial.sh
# or manually:
sudo apt update
sudo apt install -y pdal gdal-bin
```

**Conda (any OS):**

```bash
conda install -c conda-forge pdal gdal
```

**Verify PATH:**

```bash
which pdal gdalinfo gdal_grid gdal_translate gdalwarp
```

All five commands should print paths. From the project root you can run:

```bash
python -c "from mapfree.utils.dependency_check import check_geospatial_dependencies; check_geospatial_dependencies(); print('PDAL & GDAL OK')"
```

To disable geospatial stages without installing PDAL/GDAL, set in config: `enable_geospatial: false`.

### Setup

Use a virtual environment so dependencies do not affect the system Python:

```bash
git clone https://github.com/your-org/MapFree.git
cd MapFree
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Or install as an editable package (includes the `mapfree` CLI):

```bash
pip install -e .
```

### Run

**Desktop GUI:**

```bash
mapfree gui
# or
python -m mapfree.app
```

The app **opens with a placeholder** by default so it never crashes on startup. Click **"Enable 3D viewer"** in the window to turn on the OpenGL 3D viewer (software OpenGL is forced to reduce segfaults). Or run with 3D from start: `MAPFREE_OPENGL=1 mapfree gui`. To disable 3D entirely: `MAPFREE_NO_OPENGL=1 mapfree gui`

**CLI (headless pipeline):**

```bash
mapfree run <image_folder> --output <project_path>
# Open output folder and orthophoto/DTM when done (like WebODM/Metashape):
mapfree run <image_folder> -o <project_path> --open-results
```

### Hasil output: DTM & orthophoto

- Pipeline menghasilkan **sparse** → **dense** → (opsional) **geospatial** (DTM, DSM, orthophoto).
- Folder **geospatial/** (dan file `dtm.tif`, `orthophoto.tif`) **hanya dibuat** jika dependency **PDAL** dan **GDAL** terpasang. Jika tidak, tahap geospatial di-skip dan Anda hanya mendapat `sparse/`, `dense/`, `final_results/`.
- **Agar DTM dan orthophoto jadi:** pasang PDAL & GDAL (lihat [PDAL & GDAL (geospatial)](#pdal--gdal-geospatial)), lalu jalankan ulang; pipeline akan resume dari dense dan melanjutkan ke geospatial.
- **Buka hasil otomatis:** gunakan `--open-results` agar setelah selesai folder output dan (jika ada) orthophoto/DTM dibuka dengan aplikasi default sistem.

## Project Structure

**Project output layout** (per run):

```
project_output/
├── sparse/
├── dense/
└── geospatial/
    ├── dtm.tif
    ├── dtm_epsg.tif
    ├── dsm.tif
    ├── dsm_epsg.tif
    ├── orthophoto.tif
    └── orthophoto_epsg.tif
```

**Codebase:**

```
MapFree/
├── mapfree/
│   ├── app.py              # GUI entry point (python -m mapfree.app)
│   ├── core/               # Pipeline, EventBus, context, state, validation, chunking
│   ├── engines/            # COLMAP and OpenMVS engine implementations
│   ├── application/        # Controller, project/license/state stubs
│   ├── gui/                # Main window, Qt controller, workers, panels, dialogs
│   ├── utils/              # Logger, file_utils, process_utils
│   ├── config/             # Default YAML and load_config
│   ├── cli/                # CLI entry (mapfree run ...)
│   └── api/                # Backward-compat re-export of controller
├── docs/
├── tests/
├── requirements.txt
├── pyproject.toml
├── setup.cfg
├── LICENSE
├── CONTRIBUTING.md
└── CHANGELOG.md
```

## Development

**Run in dev mode**

- Install in editable mode: `pip install -e .`
- GUI: `python -m mapfree.app`
- CLI: `python -m mapfree.cli run <images> -o <project>`
- Optional: set `MAPFREE_LOG_LEVEL=DEBUG` and `MAPFREE_LOG_DIR` for file logging.

**Where the GUI lives**

- Entry: `mapfree/app.py` (creates QApplication and MainWindow).
- Window and layout: `mapfree/gui/main_window.py`.
- Panels: `mapfree/gui/panels/` (project, console, progress, viewer).
- Controller adapter and worker: `mapfree/gui/qt_controller.py`, `mapfree/gui/workers.py`.
- Dialogs and resources: `mapfree/gui/dialogs/`, `mapfree/gui/resources/` (QSS, icons).

**Where engines live**

- Engine interface and factory: `mapfree/core/engine.py` (BaseEngine, create_engine).
- Implementations: `mapfree/engines/colmap_engine.py`, `mapfree/engines/openmvs_engine.py`.
- Helpers: `mapfree/engines/base.py`, `mapfree/engines/base_engine.py` (re-exports).

Code style: PEP 8 and flake8 (see `setup.cfg` and `.flake8`). Use the `logging` module instead of `print`; see `CONTRIBUTING.md` for PR workflow.

## Roadmap

- **3D Viewer integration** — Replace viewer placeholder with OpenGL or PyQtGraph-based point cloud/mesh display.
- **Plugin system** — Load custom engines or pipeline steps via a plugin API.
- **Licensing system** — Wire license_manager and license_dialog for activation and feature gating.
- **Packaging for Windows/macOS** — PyInstaller or similar to produce standalone executables.

## License

MIT License. See [LICENSE](LICENSE) for the full text.
