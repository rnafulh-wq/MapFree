# MapFree

A lightweight, local photogrammetry pipeline for drone imagery. Designed to run on Ubuntu laptops with limited hardware (e.g. NVIDIA MX150 2GB VRAM).

**Not WebODM. No Docker. No web UI.** Python orchestrates; COLMAP does all photogrammetry computation.

## Requirements

- Ubuntu
- Python 3.8+
- [COLMAP](https://colmap.github.io/) installed and on PATH (with CUDA for SIFT and PatchMatch)
- NVIDIA GPU with ~2GB VRAM (MX150-class)

## Quick Start

```bash
# Create virtualenv and install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run pipeline on a folder of drone images (from project root)
python3 -m cli.run /path/to/images --project my_project
```

## Pipeline

1. **Project init** — Create workspace, validate images
2. **Feature extraction** — COLMAP (GPU, max ~2000 px)
3. **Matching** — COLMAP spatial or sequential
4. **Mapper** — COLMAP bundle adjustment (CPU, limited iterations)
5. **Image undistortion** — COLMAP
6. **Dense stereo** — COLMAP PatchMatch (GPU, max ~1600 px)
7. **Outputs** — Sparse and dense point clouds (PLY)

## Options

- `--config mx150` — Use MX150-safe config (default for modest hardware)
- `--dry-run` — Print COLMAP commands without executing
- `--resume` — Skip steps that already have outputs

## Outputs

Project outputs live under `projects/<name>/`:

- `sparse/` — Sparse reconstruction (cameras, points)
- `dense/` — Dense point cloud (PLY)
- `logs/` — Pipeline logs

Use outputs in CloudCompare, MeshLab, or QGIS (with conversion if needed).

## Hardware Limits

Enforced for stability on 2GB VRAM:

- Feature extraction: max image size ≈ 2000 px
- Dense reconstruction: max image size ≈ 1600 px
- CPU threads: max 4
- Matching: spatial or sequential (no exhaustive)

See `config/default.yaml` and `config/mx150.yaml` for parameters.

## License

See repository.
