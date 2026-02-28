# MapFree Architecture

## Overview

```
┌──────────────────────────────────────────────┐
│                  GUI / CLI                   │
│              Qt GUI / CLI                    │
└──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│            MapFree Core Pipeline             │
│  - ProjectContext                            │
│  - Config / Profiles                         │
│  - Hardware Detection                        │
│  - Event System                              │
└──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│                Engine Layer                  │
│                                              │
│   Sparse: COLMAP                             │
│   Dense:  COLMAP | OpenMVS (configurable)    │
│                                              │
└──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│               Output Artifacts               │
│  - Sparse model                              │
│  - Dense point cloud                         │
│  - Mesh (OpenMVS)                            │
│  - Textured mesh (OpenMVS)                   │
│  - Orthomosaic (future)                      │
└──────────────────────────────────────────────┘
```

## Principles

- **Python**: orchestration only (project setup, validation, CLI, logging, resume, GUI).
- **COLMAP**: SfM, matching, bundle adjustment, and (optionally) dense reconstruction. No reimplementation in Python.
- **OpenMVS** (optional): dense mesh pipeline (InterfaceCOLMAP → Densify → ReconstructMesh → RefineMesh → TextureMesh) when `dense_engine: openmvs`.
- **GUI**: optional desktop UI (Qt / PySide6); can run headless via CLI.

## Pipeline Order

1. **Prepare** — Resolve profile (VRAM/RAM), quality (smart scaling), chunk size; create project dirs.
2. **Sparse (COLMAP)** — Feature extraction → Matching → Mapper. Output: `sparse/0` or `sparse_merged/0` (chunked).
3. **Dense** — Chosen by config `dense_engine`:
   - **colmap**: COLMAP `image_undistorter` → `patch_match_stereo` → `stereo_fusion` → `fused.ply`.
   - **openmvs**: OpenMVSEngine (InterfaceCOLMAP → DensifyPointCloud → ReconstructMesh → RefineMesh → TextureMesh) → `openmvs/scene_textured.mvs`.
4. **Post-process** — Export sparse to `final_results/` (copy + sparse.ply); clear state when all steps complete.

## Core Pipeline Components

- **ProjectContext** — `project_path`, `image_path`, `sparse_path`, `dense_path`, `profile`.
- **Config** — YAML (`mapfree/config/default.yaml`), overridable by `--config` or `MAPFREE_CONFIG`. Keys: `dense_engine` (colmap | openmvs), `profiles`, `chunk_sizes`, `quality` presets, VRAM watchdog.
- **Profiles** — Auto-selected from VRAM (HIGH ≥4GB, MEDIUM ≥2GB, LOW ≥1GB, CPU_SAFE). Control max_image_size, matcher, use_gpu.
- **Hardware detection** — RAM (psutil), VRAM (nvidia-smi). Used for profile and quality recommendation (e.g. ≥6GB VRAM → high quality).
- **Event system** — `Event(type, message, progress)`; pipeline emits start/step/complete/error; CLI/GUI can subscribe.

## Project Layout (codebase)

- `mapfree/` — Core package: `api/` (controller), `cli/` (entry), `core/` (pipeline, context, engine, state, validation, chunking, events, logger), `engines/` (colmap_engine, openmvs_engine), `config/`, `utils/` (hardware, exif_order).
- `gui/` — Qt app (`app.py`, `main_window.py`).
- `core/` (project root) — `mapfree_core.sh` script to run pipeline from GUI.
- `config/` — YAML configs (default, mx150).
- **Per-project dir** — `sparse/`, `sparse_merged/0`, `dense/`, `openmvs/` (if OpenMVS), `final_results/`, `logs/`.

## Resume and State

- Each step checks for existing outputs; completed steps are skipped when resuming.
- State file in project path tracks completed steps (feature_extraction, matching, sparse, dense).
- OpenMVS resume: skip if `openmvs/scene_textured.mvs` exists.

---

## Minimum Specifications

### Hardware (minimum)

| Item        | Minimum |
|------------|---------|
| **CPU**    | x86_64, 4 threads (i5-class or equivalent) |
| **RAM**    | 8 GB (16 GB recommended for large datasets) |
| **GPU**    | Optional. If used: NVIDIA with ≥1 GB VRAM (2 GB recommended; &lt;2.5 GB uses CPU-safe profile) |
| **Storage**| SSD recommended; free space ≥3× size of image set for project output |

### Software

| Item        | Version / note |
|------------|----------------|
| **OS**     | Linux (Ubuntu 20.04+ / Debian, Pop!_OS); macOS/Windows possible but less tested |
| **Python** | 3.10+ (3.12 recommended) |
| **COLMAP** | 3.6+ (3.8+ recommended), on PATH or `MAPFREE_COLMAP_BIN` / config `colmap.colmap_bin` |
| **OpenMVS**| Optional; required only if `dense_engine: openmvs`. Binaries on PATH or `MAPFREE_OPENMVS_BIN_DIR` |

### Python dependencies (pyproject.toml)

- PyYAML, psutil — core.
- PySide6 — GUI only.

### GUI (optional)

- Run: `python3 -m gui.app`. Requires PySide6.

### Quality presets (smart scaling)

- **High** — Full resolution (VRAM-limited); ≥6 GB VRAM recommended.
- **Medium** — Image size ÷2; ≥2.5 GB VRAM.
- **Low** — Image size ÷4; suitable for &lt;2.5 GB VRAM or CPU-only.
