# GUI Stabilization Roadmap

Structured plan to harden the MapFree Qt GUI and 3D viewer. Phases are sequential; later phases build on the previous ones.

---

## Phase 1 — Viewer & safety

**Goal:** Decouple the viewer from the rest of the app, add guards so heavy/unsafe operations cannot freeze or crash the main process.

| Item | Status | Notes |
|------|--------|--------|
| **Decouple viewer** | ✅ Done | GUI → GL Viewer Wrapper (Safe Layer) → Render Core. Viewer only: load mesh/point cloud, render, emit signals. No PDAL/DTM/measurement in viewer (`mapfree/viewer/gl_widget.py`). |
| **Add safety guards** | ✅ Done | Mesh Buffer Guard: before GPU upload, cap at `MAX_SAFE_VERTICES`; auto-decimate in `_upload_geometry`. Memory Monitor: background thread (RSS), warn user above threshold, suggest decimation (`mapfree/gui/workers.py`). |
| **Add auto decimation** | ✅ Done | `_simplify_for_render()` for meshes &gt; `MAX_VERTICES_RENDER`; LOD above `LARGE_MESH_VERTEX_THRESHOLD`. Optional `max_vertices` for Mesh Buffer Guard. |

**Remaining (Phase 1):** None. Optional: tune `MAX_SAFE_VERTICES` / threshold from real-world usage.

---

## Phase 2 — Interaction & polish

**Goal:** Consistent interaction model, professional look, and live status so users know CRS, performance, and mode.

| Item | Status | Notes |
|------|--------|--------|
| **Interaction redesign** | ✅ Done | Scroll = zoom toward cursor; middle = pan; left = orbit (Shift = precision); Ctrl+click = measure point; ESC = cancel; double-click = focus. Arcball camera, no inertia. Distance tool: crosshair, status “Distance Mode Active”, preview line. |
| **Industrial theme** | ✅ Done | Dark industrial matte, blue accent, flat UI. Palette in `mapfree/gui/resources/styles.qss`. Layout: top toolbar, left panel (Dataset / Outputs / Measurements), GL viewer, bottom status bar. |
| **Status bar metrics** | ✅ Done | Permanent widgets: **CRS \| FPS \| Memory \| Mode**. CRS from measurement engine; Mem updated via timer (psutil); Mode = Navigation / Distance. Progress bar for pipeline and async mesh load. |

**Remaining (Phase 2):** FPS from viewer (currently “—”) if/when render loop exposes it; optional ETA in progress panel.

---

## Phase 3 — Stress & recovery

**Goal:** Prove stability under load and recover gracefully from GPU/viewer crashes so the main app stays usable.

| Item | Status | Notes |
|------|--------|--------|
| **GPU stress test** | 🔲 Todo | Add test(s): load large meshes (e.g. 5M+ vertices), multiple load/unload cycles, rapid resize. Run under `xvfb-run pytest tests/gui`. Optional: benchmark frame time and memory over time. |
| **Crash recovery fallback** | 🔲 Partial | `MainWindow._replace_with_gl_viewer()` opens viewer in a **subprocess** when OpenGL is disabled or fails, so a viewer segfault does not kill the app. Remaining: auto-detect GL crash in-process (e.g. lost context), then offer “Restart viewer” or fallback to placeholder; optional watchdog/heartbeat. |

**Remaining (Phase 3):** Implement GPU stress tests; define and implement in-process crash detection and “Restart viewer” / placeholder flow.

---

## Summary

| Phase | Focus | Status |
|-------|--------|--------|
| **1** | Decouple viewer, safety guards, auto decimation | ✅ Complete |
| **2** | Interaction redesign, industrial theme, status bar metrics | ✅ Complete |
| **3** | GPU stress test, crash recovery fallback | 🔲 In progress |

---

## How to run GUI tests

- **Headless (CI):** `pytest tests/` — tests in `tests/gui/` are skipped when `DISPLAY` is unset.
- **With display:** `xvfb-run pytest tests/gui` — runs viewer/GUI tests. See `tests/gui/README.md`.
