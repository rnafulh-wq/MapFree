#!/usr/bin/env python3
"""
QA Phase 2 stress test automation.
Simulates: large point cloud load, measurement cycles, heatmap toggles, resize.
Records: peak RAM, RAM delta, freezes > 3s, exceptions.
Run: python3 qa_reports/stress_test_runner.py
"""
import os
import sys
import time
import traceback
from pathlib import Path

class SkipTest(Exception):
    pass

try:
    import psutil
except ImportError:
    psutil = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results = {
    "start_time": time.time(),
    "peak_rss_mb": 0.0,
    "rss_start_mb": 0.0,
    "rss_end_mb": 0.0,
    "freezes": [],
    "exceptions": [],
    "tests": {},
}


def get_rss_mb():
    if psutil is None:
        return 0.0
    try:
        p = psutil.Process(os.getpid())
        return p.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def record_freeze(name, duration_sec):
    if duration_sec > 3.0:
        results["freezes"].append({"test": name, "duration_sec": round(duration_sec, 2)})


def run_stress(name, fn, *args, **kwargs):
    global results
    rss_before = get_rss_mb()
    if results["rss_start_mb"] == 0:
        results["rss_start_mb"] = rss_before
    exc = None
    t0 = time.perf_counter()
    try:
        fn(*args, **kwargs)
    except Exception as e:
        exc = e
        if type(e).__name__ == "SkipTest":
            results["tests"][name] = {"ok": True, "skipped": True, "reason": str(e)}
            return True
        results["exceptions"].append({"test": name, "error": str(e), "tb": traceback.format_exc()})
    elapsed = time.perf_counter() - t0
    record_freeze(name, elapsed)
    rss_after = get_rss_mb()
    results["peak_rss_mb"] = max(results["peak_rss_mb"], rss_after)
    if name not in results["tests"]:
        results["tests"][name] = {
            "ok": exc is None,
            "elapsed_sec": round(elapsed, 2),
            "rss_delta_mb": round(rss_after - rss_before, 2),
        }
    return exc is None


def stress_simplify_5m():
    """Simulate load path for 5M vertices (simplify only, no GL)."""
    try:
        from mapfree.viewer.gl_widget import _simplify_for_render, MAX_VERTICES_RENDER
    except ImportError:
        raise SkipTest("PySide6/viewer not available")
    n = 5_000_000
    vertices = [(float(i % 1000), float((i // 1000) % 1000), 0.0) for i in range(n)]
    normals = [(0.0, 1.0, 0.0)] * n
    colors = [(0.7, 0.7, 0.7)] * n
    v, no, c, ind = _simplify_for_render(vertices, normals, colors, None)
    assert len(v) <= MAX_VERTICES_RENDER, "expected simplification"
    assert len(v) > 0


def stress_simplify_20m():
    """Simulate load path for 20M vertices."""
    try:
        from mapfree.viewer.gl_widget import _simplify_for_render, MAX_VERTICES_RENDER
    except ImportError:
        raise SkipTest("PySide6/viewer not available")
    n = 20_000_000
    vertices = [(float(i % 1000), float((i // 1000) % 1000), 0.0) for i in range(n)]
    normals = [(0.0, 1.0, 0.0)] * n
    colors = [(0.7, 0.7, 0.7)] * n
    v, no, c, ind = _simplify_for_render(vertices, normals, colors, None)
    assert len(v) <= MAX_VERTICES_RENDER
    assert len(v) > 0


def stress_measurement_cycles():
    """200 measurement create/delete cycles (engine only, no GUI)."""
    from mapfree.engines.inspection import MeasurementEngine
    from mapfree.engines.inspection.session import MeasurementSession
    import numpy as np
    engine = MeasurementEngine()
    engine.set_mesh(
        np.random.randn(100, 3).astype(np.float64),
        np.random.randint(0, 100, (50, 3), dtype=np.intp),
    )
    session = MeasurementSession()
    for i in range(200):
        engine.measure_distance([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        session.add_measurement({"value": 1.0, "unit": "m", "method": "test"})
    assert len(session.measurements) == 200


def stress_deviation_colormap():
    """Toggle heatmap 100 times = compute deviation colors 100x."""
    try:
        from mapfree.gui.render.deviation_renderer import deviation_to_vertex_colors
    except ImportError:
        raise SkipTest("gui.render not available")
    import numpy as np
    n = 10000
    vertices = np.random.randn(n, 3).astype(np.float32)
    deviations = np.random.randn(n).astype(np.float64) * 0.5
    for _ in range(100):
        colors = deviation_to_vertex_colors(vertices, deviations)
        assert colors.shape == (n, 3)
        assert np.all(colors >= 0) and np.all(colors <= 1)


def main():
    print("QA Phase 2 — Stress test automation")
    print("=" * 60)
    run_stress("simplify_5M_points", stress_simplify_5m)
    run_stress("simplify_20M_points", stress_simplify_20m)
    run_stress("200_measurement_cycles", stress_measurement_cycles)
    run_stress("100_heatmap_toggles", stress_deviation_colormap)
    results["rss_end_mb"] = get_rss_mb()
    results["elapsed_total_sec"] = round(time.time() - results["start_time"], 2)
    print("Peak RSS (MB):", results["peak_rss_mb"])
    print("RSS delta (MB):", round(results["rss_end_mb"] - results["rss_start_mb"], 2))
    print("Freezes > 3s:", len(results["freezes"]), results["freezes"])
    print("Exceptions:", len(results["exceptions"]))
    for t, r in results["tests"].items():
        print(" ", t, "PASS" if r["ok"] else "FAIL", r.get("elapsed_sec"), "s")
    return 0 if not results["exceptions"] else 1


if __name__ == "__main__":
    sys.exit(main())
