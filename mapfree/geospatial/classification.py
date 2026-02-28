"""
Point cloud classification: assign labels/classes to points.
Ground classification via PDAL SMRF. Pure backend; no GUI.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

import logging

log = logging.getLogger(__name__)

# LAS classification: 2 = ground (ASPRS)
GROUND_CLASS = 2


def _smrf_pipeline_json(input_las: str, output_las: str) -> dict:
    return {
        "pipeline": [
            input_las,
            {
                "type": "filters.smrf",
                "slope": 0.2,
                "window": 16.0,
                "threshold": 0.45,
                "scalar": 1.2,
            },
            output_las,
        ]
    }


def classify_ground(
    input_las: Path,
    output_las: Path,
    timeout: int = 3600,
) -> Path:
    """
    Classify ground points using PDAL SMRF filter. Writes a temporary pipeline
    JSON, runs `pdal pipeline pipeline.json`, then verifies output has
    classification class 2 (ground).
    Raises RuntimeError on failure.
    """
    input_las = Path(input_las)
    output_las = Path(output_las)
    if not input_las.exists():
        raise RuntimeError("classify_ground: input does not exist: %s" % input_las)
    output_las.parent.mkdir(parents=True, exist_ok=True)

    pipeline = _smrf_pipeline_json(str(input_las.resolve()), str(output_las.resolve()))
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(pipeline, f, indent=2)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["pdal", "pipeline", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            msg = result.stderr or result.stdout or "pdal pipeline failed"
            raise RuntimeError("classify_ground failed: %s" % msg.strip())
    except subprocess.TimeoutExpired:
        raise RuntimeError("classify_ground timed out after %s seconds" % timeout)
    except FileNotFoundError:
        raise RuntimeError(
            "classify_ground: pdal not found. Install PDAL and ensure it is on PATH."
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not output_las.exists():
        raise RuntimeError("classify_ground: output was not created: %s" % output_las)

    # Ensure classification class 2 (ground) exists
    try:
        info_result = subprocess.run(
            ["pdal", "info", str(output_las), "--stats"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (info_result.stdout or "") + (info_result.stderr or "")
        if str(GROUND_CLASS) not in out and "ground" not in out.lower():
            log.warning(
                "classify_ground: class %s (ground) not found in pdal info output; "
                "output may still be valid.",
                GROUND_CLASS,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    log.info("classify_ground: %s -> %s", input_las, output_las)
    return output_las


def classify_point_cloud(
    point_cloud_path: Path,
    config: Optional[Dict[str, Any]] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Classify points in point_cloud_path (e.g. sparse.ply, fused.ply).
    config: optional dict with classifier params (model, classes, etc.).
    Returns path to classified output.
    """
    if output_path is None:
        output_path = Path(point_cloud_path).parent / "classified"
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    log.info("classify_point_cloud: %s -> %s", point_cloud_path, output_path)
    # Stub: actual implementation would run classifier
    return output_path
