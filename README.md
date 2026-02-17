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

Optional: `--chunk-size 300`, `--force-profile LOW`.

**Legacy CLI** (dari root repo):

```bash
python -m cli.main <image_path> <project_path>
```

**GUI** (PySide6):

```bash
python gui/app.py
```

Atau `python -m gui.app` jika package terinstall (`pip install -e .`).

## Setup

```bash
pip install -e .
```

PySide6 masuk di `pyproject.toml`. CLI dan GUI memakai engine yang sama lewat `MapFreeController`.
