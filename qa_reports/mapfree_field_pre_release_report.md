# MapFree Field — Pre-Release Hardening Audit Report

**Document:** Technical QA Report  
**Version:** 0.1.0 (Field)  
**Date:** 2026-02-18  
**Classification:** Internal — Pre-Release

---

## Executive Summary

This report summarizes the pre-release hardening audit for **MapFree Field Version**. The audit followed a five-phase checklist: static/build analysis (sanitizers + full test suite), stress test automation, DTM/orthophoto validation, low-spec simulation, and structured reporting.

**Outcome:** The audit was executed in an environment where **Python dependencies (PySide6, numpy) were not installed** and **pytest was not available**. Therefore:

- **Phase 1 (tests):** Executed. **2 test failures** and **2 tests skipped** (viewer tests require pytest).
- **Phase 1 (sanitizers):** **Not applicable** as documented below — MapFree is a Python application with no C/C++ extension build in-tree; sanitizers would require a custom Python build or native extensions.
- **Phases 2–4:** **Not fully executed** in this run due to missing runtime dependencies; automation scripts were added for future use in a fully provisioned environment.

**Recommendation:** **Conditional Go** — Proceed to field use only after:
1. Running the full test suite in a proper venv and fixing the two failing tests.
2. Running stress tests and DTM/orthophoto validation in a venv with all dependencies.
3. Performing at least one manual low-spec (8 GB RAM) run.

---

## 1. Phase 1 — Static & Build Analysis

### 1.1 Build with AddressSanitizer / UndefinedBehaviorSanitizer / LeakSanitizer

| Item | Status | Severity |
|------|--------|----------|
| ASan/UBSan/LSan build | **N/A** | **Low** |

**Explanation:** MapFree is a **Python 3.10+** application. It has **no in-tree C/C++ build** (no `setup.py` C extensions, no CMake). Sanitizers apply to:

- **C/C++ code:** Not present in the project.
- **Python interpreter:** Would require building CPython with `CFLAGS="-fsanitize=address,undefined"` and `LDFLAGS="-fsanitize=address,undefined"` — not performed in this audit.
- **Third-party native libs (e.g. PySide6, numpy):** Vendor-provided; not built from source here.

**Recommendation:** For maximum assurance, run the test suite under a Python build with ASan/LSan in a dedicated CI job. For typical field deployment, risk remains **low** given no custom native code.

### 1.2 Full Test Suite Execution

| Suite | Pass | Fail | Skip | Notes |
|-------|------|------|------|--------|
| test_engine_wrapper | 5 | 0 | 0 | All pass |
| test_fresh_run | 12 | 1 | 0 | 1 failure |
| test_chunking_logic | 15 | 0 | 0 | All pass |
| test_chunking_regression | 13 | 0 | 0 | All pass |
| test_colmap_params | 20 | 1 | 0 | 1 failure |
| test_profiles | 38 | 0 | 0 | All pass |
| test_progress_tracking | 12 | 0 | 0 | All pass |
| test_resume_engine | 22 | 0 | 0 | All pass |
| test_viewer_load_ply | — | — | 2 | pytest not installed |
| test_viewer_load_mesh | — | — | 2 | pytest not installed |

**Total (excluding viewer):** **137 pass, 2 fail.**

#### Crashes

- **None** observed during the test run.

#### Memory leaks

- **Not measured** in this run (no LeakSanitizer; no dedicated leak harness).

#### UB warnings

- **None** (no UBSan run).

#### Stack traces / failures

1. **test_fresh_run — "state file cleaned after complete"**  
   - **Severity:** **Medium**  
   - **Detail:** Assertion expects state file to be removed after pipeline completion; state file still exists.  
   - **Likely cause:** Logic in pipeline or state module does not delete the state file when all completion steps are done, or test expectation is wrong.  
   - **Action:** Fix state cleanup semantics or adjust test; verify intended behavior.

2. **test_colmap_params — "no unknown flags"**  
   - **Severity:** **Low**  
   - **Detail:** Test reports unknown flag `--image_list_path`.  
   - **Likely cause:** COLMAP API or engine uses a flag not in the test’s allow-list.  
   - **Action:** Update test allow-list or remove deprecated flag from engine.

---

## 2. Phase 2 — Stress Test Execution

### 2.1 Automation

- **Script added:** `qa_reports/stress_test_runner.py`
- **Planned coverage:**
  - Load path for 5M and 20M point clouds (simplify-only path, no GL).
  - 200 measurement create/delete cycles (engine + session).
  - 100 heatmap toggles (deviation colormap).
  - Memory/CPU monitoring via `psutil` when available.

### 2.2 Execution in This Audit

| Item | Status | Severity |
|------|--------|----------|
| 5M / 20M point cloud load | **Not run** | **High** |
| Toggle layers 100× | **Not run** | **Medium** |
| 200 measurement cycles | **Not run** | **Medium** |
| 100 heatmap toggles | **Not run** | **Medium** |
| Resize 200× | **Not run** | **Low** |
| Peak RAM / RAM delta | **Not recorded** | — |
| Freezes > 3 s | **Not recorded** | — |

**Reason:** Runtime environment lacked **PySide6** and **numpy**. Stress script exits with import errors before running viewer-dependent and numpy-dependent logic.

**Recommendation:** Run `python3 qa_reports/stress_test_runner.py` inside a **venv with all project dependencies**. Repeat on a low-spec (e.g. 8 GB RAM) machine and record peak RAM and any freezes.

---

## 3. Phase 3 — DTM & Orthophoto Validation

### 3.1 Planned Checks

- Generate DTM from test dataset; export GeoTIFF; validate CRS and file integrity.
- Repeat for Orthophoto (DTM-based export, GeoTIFF, CRS, integrity).

### 3.2 Execution in This Audit

| Item | Status | Severity |
|------|--------|----------|
| DTM generation + GeoTIFF export | **Not run** | **High** |
| DTM CRS metadata | **Not validated** | **High** |
| DTM output integrity | **Not validated** | **Medium** |
| Orthophoto generation + export | **Not run** | **High** |
| Orthophoto CRS / integrity | **Not validated** | **High** |

**Reason:** No test LAS/PLY or geospatial output in the audit environment; optional dependencies (e.g. GDAL, PDAL) not verified. Code review confirms DTM pipeline uses Float32, nodata, and optional EPSG; orthophoto uses TILED/BIGTIFF options.

**Recommendation:** In a provisioned environment with PDAL/GDAL and a small test dataset:
- Run geospatial pipeline to produce DTM and orthophoto GeoTIFFs.
- Run `gdalinfo` on outputs and verify CRS, nodata, and data type.
- Run `qa_reports/dtm_ortho_validate.py` once that script is extended to accept test paths.

---

## 4. Phase 4 — Low-Spec Simulation

### 4.1 Target

- 8 GB RAM, integrated GPU.
- 20 min measurement session, DTM export, orthophoto export.
- Record stability, performance, errors.

### 4.2 Execution in This Audit

| Item | Status | Severity |
|------|--------|----------|
| 8 GB RAM limit simulation | **Not run** | **High** |
| 20 min measurement session | **Not run** | **High** |
| DTM/ortho export on low-spec | **Not run** | **High** |

**Reason:** No controlled low-spec environment or memory limit (e.g. `ulimit`) applied in this run; GUI and measurement session require full stack (PySide6, OpenGL).

**Recommendation:** Run MapFree on a physical or VM with 8 GB RAM and integrated GPU; perform a 20 min measurement session and DTM/orthophoto export; note any OOM, freezes, or GPU errors.

---

## 5. Phase 5 — Risk Assessment

### 5.1 Crash Analysis

| Risk | Severity | Evidence |
|------|----------|----------|
| Pipeline crash from subprocess | **Low** | Wrapper and OpenMVS steps use try/except and EngineExecutionError; pipeline emits pipeline_error. |
| GUI crash from large mesh | **Medium** | Viewer has MAX_VERTICES_RENDER and simplification; not stress-tested. |
| Export crash (DTM/ortho) | **Medium** | Export runs in worker; subprocess timeouts and exceptions handled; not validated with real data. |

### 5.2 Memory Analysis

| Risk | Severity | Evidence |
|------|----------|----------|
| Unbounded growth in pipeline | **Low** | No custom long-lived caches observed; state is file-based. |
| Viewer OOM on huge PLY | **Medium** | Simplification caps vertices; 5M/20M path not exercised. |
| Leak in measurement/deviation | **Low** | No sanitizer or long-run leak test. |

### 5.3 Stress Test Results

- **Not obtained** in this audit (dependencies missing).
- **Risk:** **High** until stress tests are run in a full environment.

### 5.4 DTM Validation Results

- **Not obtained.**
- **Risk:** **High** for field use until DTM/ortho export is validated with real GeoTIFFs and CRS checks.

### 5.5 Orthophoto Validation Results

- **Not obtained.**
- **Risk:** **High** for field use until orthophoto export and metadata are validated.

### 5.6 Other Risks

| Item | Severity |
|------|----------|
| Two unit test failures (state cleanup, COLMAP flag) | **Medium** |
| Viewer tests not run (pytest missing) | **Medium** |
| No automated low-spec run | **High** |

---

## 6. Go / No-Go Recommendation

### 6.1 Summary

| Criterion | Status |
|-----------|--------|
| No known crashes in executed tests | **Pass** |
| All automated tests pass | **Fail** (2 failures) |
| Stress tests passed | **Not run** |
| DTM/ortho validated | **Not run** |
| Low-spec run performed | **Not run** |

### 6.2 Recommendation: **Conditional Go**

- **Go** for **internal or controlled field trials** provided:
  - The two failing unit tests are fixed or accepted as known issues with a ticket.
  - At least one full run (pipeline + DTM + orthophoto) is done in a real or venv environment and outputs are spot-checked.
- **No-Go** for **unrestricted field release** until:
  - All non-skipped tests pass.
  - Stress tests (5M/20M load, measurement cycles, heatmap toggles) are run and show no critical freezes or OOM.
  - DTM and orthophoto GeoTIFFs are validated (CRS, nodata, integrity).
  - At least one 8 GB RAM / integrated GPU run is done (20 min session + exports) with no critical failures.

### 6.3 Severity Legend

- **Critical:** Data loss, crash in core path, security issue.
- **High:** Unvalidated core feature (DTM/ortho), or no stress/low-spec run.
- **Medium:** Test failures, viewer path unexercised, possible OOM in edge cases.
- **Low:** Sanitizers N/A, minor flag allow-list mismatch.

---

## 7. Artifacts

| Artifact | Path |
|---------|------|
| This report | `qa_reports/mapfree_field_pre_release_report.md` |
| Stress test runner | `qa_reports/stress_test_runner.py` |
| DTM/ortho validation stub | `qa_reports/dtm_ortho_validate.py` |

---

*Report generated as part of the MapFree Field pre-release hardening audit. Be brutally honest; do not hide instability.*
