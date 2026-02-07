# MapFree

MapFree runs a 3D reconstruction pipeline (feature extraction → matching → sparse → dense) via a configurable engine and profiles.

## Layout

- **mapfree/core** — Events, `ProjectContext`, `Pipeline`, logger
- **mapfree/engines** — `BaseEngine`, `ColmapEngine` (placeholder)
- **mapfree/profiles** — `MX150_PROFILE`
- **mapfree/api** — `MapFreeController`
- **cli** — `cli/main.py` (CLI entry)
- **gui** — PySide6 app and main window

## Run

**CLI** (from repo root):

```bash
pip install -e .
python -m cli.main <image_path> <project_path>
```

**GUI**:

```bash
pip install PySide6
python -m gui.app
```

Example:

```bash
python -m cli.main images project_out
```
