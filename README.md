# MapFree — Modular photogrammetry engine

Pipeline 3D (feature extraction → matching → sparse → dense) lewat engine + profile. Satu **core** (pipeline, context, events) dipakai oleh **CLI** dan **GUI** lewat `MapFreeController`.

## Layout

```
mapfree/
  core/       pipeline.py, context.py, events.py, hardware.py, chunking.py
  engines/    base.py, colmap_engine.py (colmap.py)
  profiles/   mx150.py
  api/        controller.py
  cli.py      mapfree run <images> --output <project>
cli/          main.py (legacy)
gui/          app.py, main_window.py
```

## Usage

**Automatic pipeline** (hardware detection, profile, optional chunking, merge, dense):

```bash
mapfree run <image_folder> --output <project>
# or: python -m mapfree.cli run <image_folder> -o <project>
```

Final sparse model: `sparse_merged/0/` (chunked) or `sparse/0/` (single). The pipeline also exports to `final_results/` (sparse copy + `sparse.ply`).

Optional: `--chunk-size 300`, `--force-profile LOW`.

**Legacy CLI** (dari root repo):

```bash
python -m cli.main <image_path> <project_path>
```

**GUI (Qt / PySide6)** — jendela sederhana:

```bash
python3 -m gui.app
```

## Setup

```bash
cd /path/to/MapFree
pip install -e .
```

Jika muncul error **externally-managed-environment**, pakai virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
pip install -e .
python3 -m gui.app
```

Dependencies: PySide6, PyYAML, psutil. CLI dan GUI memakai engine yang sama lewat `MapFreeController`.
