# GUI tests

Tests that need a display (Qt / OpenGL viewer). They live in `tests/gui/` so they can be run or skipped separately.

## Run locally (with display)

```bash
xvfb-run pytest tests/gui
```

Use the project root as working directory and ensure `mapfree` is on `PYTHONPATH` (e.g. `pip install -e .` or `export PYTHONPATH=.`).

## CI / headless

- **Skip automatically**: When `DISPLAY` is not set (e.g. plain `pytest tests/` in headless CI), all tests in `tests/gui/` are **skipped** (no segfault, no Qt/GL init).
- **Run in CI**: To run GUI tests in CI, use a job that runs:

  ```bash
  xvfb-run pytest tests/gui
  ```

  (Install `xvfb` if needed: `apt install xvfb`.)

## Marker

GUI tests are associated with the `gui` marker. List markers:

```bash
pytest --markers
```
