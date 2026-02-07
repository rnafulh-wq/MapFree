# MapFree

MapFree runs a 3D reconstruction pipeline (feature extraction → matching → sparse → dense) via a configurable engine and profiles. Architecture is modular: **core** (events, context, pipeline) + **engines** (e.g. COLMAP) + **API controller** + **CLI** / **GUI** entry points.

## Layout (GUI-ready)

| Layer        | Path                | Role |
|-------------|---------------------|------|
| Core        | `mapfree/core/`     | `Event`, `ProjectContext`, `Pipeline`, logger |
| Engines     | `mapfree/engines/`  | `BaseEngine`, `ColmapEngine` |
| Profiles    | `mapfree/profiles/` | `MX150_PROFILE` (SIFT/dense limits, GPU) |
| API         | `mapfree/api/`      | `MapFreeController` — single entry for run |
| CLI         | `cli/main.py`       | `python -m cli.main <images> <project>` |
| GUI         | `gui/app.py`        | PySide6 app; `gui/main_window.py` (progress, worker thread) |

## Setup

```bash
pip install -e .
# GUI needs PySide6 (in pyproject.toml)
```

## Run

**CLI** (from repo root):

```bash
python -m cli.main <image_path> <project_path>
```

Example:

```bash
python -m cli.main images project_out
```

**GUI**:

```bash
python -m gui.app
```

- Uses `MapFreeController` in a worker thread; progress bar and label show pipeline events.
- Demo button runs with `images` → `project_gui`; you can later add dialogs for paths.
