# Coverage Gap Analysis — Fase 1
_Generated: 2026-03-04 | Target Fase 1: overall ≥ 50%_

---

## Hasil Coverage Saat Ini

Test suite yang dijalankan:
- `tests/core/` — EventBus, Pipeline, Exceptions (41 tests)
- `tests/utils/` — Logging (7 tests)
- `tests/integration/` — CLI end-to-end (5 tests)
- `tests/gui/` dikecualikan (memerlukan Qt display / xvfb)

```
Scope                   Coverage
mapfree (total)          12%   ← GUI + viewer menarik angka ke bawah
mapfree.core             ~65%  ← target sudah baik untuk modul utama
mapfree.application      ~40%
mapfree.engines          ~15%  ← butuh binary COLMAP/OpenMVS
mapfree.geospatial        <5%  ← butuh PDAL/GDAL
mapfree.gui               0%   ← memerlukan Qt display
mapfree.viewer            0%   ← memerlukan OpenGL context
```

---

## Analisis Per Modul

| Modul | Coverage % | Lines Uncovered (est.) | Priority |
|---|---|---|---|
| `core/event_bus.py` | 93% | ~2 | ✅ Baik |
| `core/exceptions.py` | 100% | 0 | ✅ Selesai |
| `core/context.py` | 100% | 0 | ✅ Selesai |
| `core/logger.py` | 78% | ~27 | 🟡 Medium |
| `core/pipeline.py` | 53% | ~181 | 🟡 Medium |
| `core/validation.py` | 78% | ~5 | 🟡 Medium |
| `core/hardware.py` | 78% | ~2 | 🟡 Medium |
| `core/state.py` | 66% | ~26 | 🟡 Medium |
| `core/config/__init__.py` | 67% | ~26 | 🟡 Medium |
| `application/controller.py` | 77% | ~22 | 🟡 Medium |
| `core/chunking.py` | 36% | ~48 | 🔴 Gap |
| `core/final_results.py` | 31% | ~35 | 🔴 Gap |
| `core/wrapper.py` | 10% | ~129 | 🔴 Gap (butuh binary mock) |
| `engines/colmap_engine.py` | ~10% | ~300 | 🔴 Gap (butuh COLMAP mock) |
| `engines/mvs_openmvs.py` | 0% | semua | 🔴 Gap |
| `geospatial/*` | <5% | semua | 🔴 Gap (butuh PDAL/GDAL) |
| `gui/*` | 0% | semua | 🔵 Butuh Qt/xvfb |
| `viewer/*` | 0% | semua | 🔵 Butuh OpenGL |

---

## Alasan Coverage Rendah di Total

### 1. GUI Modules (gui/, viewer/)
Butuh Qt QApplication dan OpenGL context. Di CI headless:
- Jalankan dengan `xvfb-run pytest tests/gui` (Linux)
- Atau `QT_QPA_PLATFORM=offscreen` + skip OpenGL tests
- **Action**: aktifkan `xvfb-run` di GitHub Actions untuk job terpisah

### 2. Engine Wrappers (wrapper.py, colmap_engine.py)
Butuh binary COLMAP aktual atau mock yang lebih lengkap:
```
core/wrapper.py: 10%  ← run_command, run_process_streaming butuh subprocess mock
engines/colmap_engine.py: ~10%  ← feature_extraction, matching, sparse butuh mock COLMAP
```
- **Action**: buat mock subprocess di `tests/engines/test_colmap_engine.py`

### 3. Geospatial (geospatial/)
Butuh PDAL dan GDAL terinstall. Tidak tersedia di CI default.
- **Action**: tambahkan CI job dengan PDAL/GDAL (conda-forge) atau skip dengan mock

---

## Target Fase 1: Strategi Mencapai ≥ 50%

Untuk mencapai target 50% pada akhir Fase 1, fokus pada:

1. **Tambah mock subprocess di test_engine_wrapper.py** (pytest-style)
   - `run_command` dengan mock Popen → +5-8% coverage
   
2. **Mock colmap_engine.py subprocess calls**
   - `tests/engines/test_colmap_engine.py` → +4-6%
   
3. **Tambah test untuk core/chunking.py**
   - `tests/core/test_chunking.py` → +3-4%
   
4. **Tambah test untuk core/final_results.py**
   - `tests/core/test_final_results.py` → +2-3%

5. **Aktifkan xvfb dalam GitHub Actions untuk GUI tests**
   - Tambah job `test-gui` dengan `xvfb-run` → +10-15%

**Estimasi coverage setelah action plan di atas: ~30-40% (core+app+engines)**
**Dengan GUI tests via xvfb: estimasi ≥ 50% tercapai**

---

## Tasks Lanjutan (tasks/fase1_extra.md)

Dibuat terpisah untuk menutup gap coverage yang tersisa.

Prioritas:
- [ ] `tests/engines/test_colmap_engine.py` — mock subprocess calls
- [ ] `tests/core/test_chunking.py` — split_dataset, count_images, merge
- [ ] `tests/core/test_final_results.py` — export_sparse_to_ply mock
- [ ] GitHub Actions: tambah job `test-gui` dengan xvfb-run
- [ ] `tests/core/test_wrapper.py` — run_command dengan mock Popen
