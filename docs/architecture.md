# MapFree Architecture

## Principles

- **Python**: orchestration only (project setup, validation, CLI generation, logging, resume).
- **COLMAP**: all SfM, matching, BA, and dense reconstruction. No reimplementation in Python.
- **No Docker, no WebODM, no web UI.**

## Pipeline Order (Fixed)

1. Project initialization (Python)
2. COLMAP `feature_extractor` (GPU, limited resolution)
3. COLMAP matcher (spatial or sequential)
4. COLMAP `mapper` (CPU bundle adjustment, limited iterations)
5. COLMAP `image_undistorter`
6. COLMAP `patch_match_stereo` (GPU, limited resolution)
7. Outputs: sparse + dense point clouds

## Hardware Constraints

Target: Ubuntu, i5-class CPU (max 4 threads), NVIDIA MX150 2GB VRAM.

- Feature extraction: max image size ≈ 2000 px
- Dense reconstruction: max image size ≈ 1600 px
- Prefer spatial/sequential matching; avoid exhaustive
- Limit CPU threads to 4

## Project Layout

- `config/` — YAML configs (default, mx150)
- `pipeline/` — Python orchestration (project, steps, COLMAP runner, exporter, logging)
- `cli/` — Entry point (`run.py`)
- `projects/` — One folder per project (images, sparse, dense, logs)
- `logs/` — Global pipeline logs

## Resume and Dry-Run

- Each step checks for existing outputs; completed steps are skipped when resuming.
- `--dry-run` prints all COLMAP commands without executing.
