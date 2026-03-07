# MapFree Engine

**Native Desktop Photogrammetry Engine**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/rnafulh-wq/MapFree)

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

MapFree is intended to run from the **mapfree_engine** conda environment so that Python, GDAL, PDAL, and MapFree share one environment (single-install, portable).

### Quick start (recommended)

```bash
# Clone and enter repo
git clone https://github.com/rnafulh-wq/MapFree.git
cd MapFree

# Create conda environment and install MapFree
conda env create -f environment.yml
conda activate mapfree_engine
pip install -e .

# Run MapFree (always activate the env first)
conda activate mapfree_engine
python -m mapfree
```

**Windows:** Use `scripts\install_windows.bat` for one-click install (conda detection, env create, MapFree install, verification, desktop shortcut). Then run `scripts\mapfree_launcher.bat` or the Desktop shortcut to start MapFree. PySide6 is installed from conda-forge by the installer to avoid Qt DLL conflicts with COLMAP/GDAL.

### Requirements

- Python 3.11 (via `environment.yml`)
- **Conda** — Miniconda or Anaconda. MapFree and its dependencies (GDAL, PDAL, PySide6, etc.) are installed into the **mapfree_engine** environment. **PySide6 must be installed via conda-forge** (as in `environment.yml`), not pip, to avoid Qt DLL conflicts with COLMAP/GDAL.
- **COLMAP** — install separately and on PATH (or set `MAPFREE_COLMAP` / config). Not included in the conda env.
- **OpenMVS** — optional; install separately if using dense mesh pipeline. COLMAP dense is the default.
- **PDAL and GDAL** — included in `environment.yml` (conda-forge); used for geospatial stages (DTM, orthophoto).

### PDAL & GDAL (geospatial)

When using the **mapfree_engine** environment, PDAL and GDAL are installed via `environment.yml` (conda-forge). No extra step needed.

**If not using the conda env** (e.g. system Python or venv):

- **Ubuntu / Debian:** `sudo apt install pdal gdal-bin` (or `./scripts/install_geospatial.sh`).
- **Conda:** `conda install -c conda-forge pdal gdal`.

**Verify (inside mapfree_engine):**

```bash
conda activate mapfree_engine
python -c "from mapfree.utils.dependency_check import check_geospatial_dependencies; check_geospatial_dependencies(); print('PDAL & GDAL OK')"
```

To disable geospatial stages, set in config: `enable_geospatial: false`.

### Alternative setup (venv / system Python)

If you prefer a virtualenv instead of conda:

```bash
git clone https://github.com/rnafulh-wq/MapFree.git
cd MapFree
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

You must install PDAL and GDAL separately and ensure they are on PATH. **Recommended:** use the **mapfree_engine** conda env for a single, consistent setup.

### Run

Always activate the **mapfree_engine** environment first, then run MapFree:

```bash
conda activate mapfree_engine
python -m mapfree
```

**Desktop GUI:** The above starts the GUI by default. You can also run:

```bash
conda activate mapfree_engine
mapfree gui
# or
python -m mapfree.app
```

The app **opens with a placeholder** by default so it never crashes on startup. Click **"Enable 3D viewer"** in the window to turn on the OpenGL 3D viewer (software OpenGL is forced to reduce segfaults). Or run with 3D from start: `MAPFREE_OPENGL=1 mapfree gui`. To disable 3D entirely: `MAPFREE_NO_OPENGL=1 mapfree gui`

> **Note — 3D Viewer (Experimental):** The OpenGL viewer is experimental. It may crash or produce visual artefacts depending on GPU driver and platform. It runs in a separate process to protect the main window. If you experience instability, use `MAPFREE_NO_OPENGL=1` to keep it disabled.

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

**Run in dev mode (inside mapfree_engine)**

- Create env and install: `conda env create -f environment.yml && conda activate mapfree_engine && pip install -e .`
- GUI: `conda activate mapfree_engine && python -m mapfree.app`
- CLI: `conda activate mapfree_engine && python -m mapfree.cli run <images> -o <project>`
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
