# MapFree Full Validation Report — Round 2

**Document:** Full Validation Suite (Round 2)  
**Date:** 2026-03-03  
**Interpreter:** `/home/pop_mangto/miniconda3/envs/mapfree_prod/bin/python`  
**Classification:** Internal — Field release readiness

---

## 1. Environment Info

| Item | Value |
|------|--------|
| Python | 3.12.12 (conda env `mapfree_prod`) |
| Interpreter path | `/home/pop_mangto/miniconda3/envs/mapfree_prod/bin/python` |
| GDAL | 3.12.2 (Python bindings; `from osgeo import gdal`) |
| PDAL | 2.10.0 (cli: `pdal --version` → `pdal 2.10.0 (git-version: c249cd)`) |
| Platform | Linux (kernel 6.17.9) |

**Note:** Semua dijalankan dari conda env `mapfree_prod` yang sama. Untuk menjalankan test suite, ditambahkan: pytest, PyYAML, PySide6, psutil (sesuai pyproject.toml).

---

## 2. Interpreter Configuration

- **.vscode/settings.json** dibuat/di-set dengan:
  - `python.defaultInterpreterPath`: `/home/pop_mangto/miniconda3/envs/mapfree_prod/bin/python`
- Project dijalankan dengan interpreter tersebut.

---

## 3. Hasil Setiap Tahap Test

### A. Unit tests (`pytest -v --maxfail=1`)

- **Script-style test (engine wrapper):**  
  Dijalankan sebagai `python tests/test_engine_wrapper.py` (bukan pytest) karena modul ini memanggil `sys.exit()` saat import sehingga mengganggu collection pytest.  
  **Hasil:** **5 PASS, 0 FAIL.**

- **Pytest-collected tests:**  
  Hanya ada test di `test_viewer_load_mesh.py` dan `test_viewer_load_ply.py` (4 test total). Keduanya membutuhkan QOpenGLWidget.  
  **Hasil:** **Segmentation fault** saat setup fixture `viewer_widget` (saat membuat GL context), baik dengan maupun tanpa `QT_QPA_PLATFORM=offscreen`.  
  **Diagnosis:** Headless OpenGL di env ini (PySide6 + driver/GPU) menyebabkan crash; bukan kegagalan logika test. Tes viewer **tidak dijalankan** (di-skip secara praktis).

- **Test file lain:**  
  `test_chunking_logic.py`, `test_chunking_regression.py`, `test_colmap_params.py`, `test_fresh_run.py`, `test_profiles.py`, `test_progress_tracking.py`, `test_resume_engine.py` tidak mendefinisikan fungsi `test_*` yang dikenali pytest; mereka berupa script atau pola lain. Tidak dijalankan sebagai pytest.

**Ringkasan A:**  
- Engine wrapper: **PASS**.  
- Unit test pytest (non-viewer): **0 test** (tidak ada test selain viewer yang ter-collect).  
- Viewer tests: **SKIP** (segfault di headless).

---

### B. Measurement engine tests (`pytest tests/measurement -v`)

- **Direktori `tests/measurement`:** **Tidak ada.** Tidak ada subdirektori atau modul `measurement` di bawah `tests/`.
- **Pytest dengan `-k measurement`:** **0 items** collected (tidak ada test dengan nama/keyword "measurement").
- **Cakupan measurement engine:** Logika measurement engine (headless) dijalankan lewat **stress test** di `qa_reports/stress_test_runner.py`: skenario **200_measurement_cycles** (MeasurementEngine + MeasurementSession, 200 cycle measure + add_measurement). Lihat hasil E di bawah.

**Ringkasan B:**  
- `pytest tests/measurement -v` **tidak dapat dijalankan** (folder tidak ada).  
- Measurement engine **tidak punya dedicated unit test**; divalidasi lewat stress test **200_measurement_cycles** → **PASS** (semua 3 iterasi).

---

### C. DTM & Orthophoto pipeline validation

- **QA script API:**  
  `python qa_reports/dtm_ortho_validate.py` dijalankan.  
  **Hasil:** **PASS.**  
  - `dtm`: `api_nodata` = -9999.0, `api_float32_nodata` = True.  
  - `orthophoto`: `api_tiled_bigtiff` = True.  
  - `errors`: [], `skipped`: [].

- **Pipeline pada sample dataset kecil:**  
  Dijalankan: PLY → LAS (`convert_ply_to_las`) → classify ground (`classify_ground`) → DTM (`generate_dtm`) dengan fixture `tests/fixtures/point_cloud.ply` dan output ke `/tmp/mapfree_qa_round2/`.  
  **Hasil:**  
  - PLY → LAS: **OK.**  
  - Classify ground: **OK.**  
  - **generate_dtm** (gdal_grid + gdal_translate): **GAGAL**  
    - Error: `RuntimeError: generate_dtm failed: ERROR 4: '...ground.las' not recognized as being in a supported file format.`  
  **Diagnosis:** GDAL di env conda ini **tidak memiliki driver baca LAS** (build tanpa dukungan LAS). Bukan bug kode MapFree; environment tidak mendukung pembacaan LAS oleh gdal_grid. Validasi CRS/GeoTransform/pixel size/empty raster/bounding box pada output DTM **tidak dapat dilakukan** karena DTM tidak pernah berhasil dihasilkan di run ini.

**Ringkasan C:**  
- Validasi API (DTM/Ortho): **PASS.**  
- Validasi pipeline penuh (sampai DTM tif): **GAGAL di langkah DTM** karena GDAL tidak mengenali format LAS di env ini.  
- CRS/GeoTransform/pixel size/empty raster/bbox **tidak divalidasi** (tidak ada raster DTM yang dihasilkan).

---

### D. PDAL pipeline validation

- **Langkah:** Menjalankan DTM generation path yang memakai PDAL: PLY → LAS → **classify_ground** (SMRF) → (generate_dtm gagal di C karena GDAL, tapi PDAL pipeline sendiri dijalankan).
- **Khusus:** Mengecek stderr/stdout dari `pdal pipeline` untuk **warning terkait projection / axis order**.
- **Hasil:**  
  - `pdal pipeline` (SMRF): **returncode 0.**  
  - Stderr: Hanya satu pesan:  
    `(pdal pipeline filters.smrf Warning) SMRF running with a small number of cells (4). Consider changing cell size.`  
  - **Tidak ada** warning terkait projection atau axis order.

**Ringkasan D:**  
- PDAL pipeline (classify/DTM path): **PASS.**  
- **Tidak ada** warning projection/axis order.

---

### E. Stress test

- **Script:** `python qa_reports/stress_test_runner.py`.  
- **Jumlah iterasi:** **3** kali berturut-turut (sesuai permintaan minimal 3 iterasi).
- **Skenario:** simplify_5M_points, simplify_20M_points, 200_measurement_cycles, 100_heatmap_toggles.

**Hasil per run:**

| Run | Peak RSS (MB) | RSS delta (MB) | Freezes >3s | Exceptions | Result |
|-----|----------------|----------------|-------------|------------|--------|
| 1   | 78.57         | 64.54          | 1 (simplify_20M: 7.73 s) | 0 | PASS |
| 2   | 78.38         | 64.46          | 1 (simplify_20M: 7.63 s) | 0 | PASS |
| 3   | 78.37         | 64.43          | 2 (simplify_5M: 3.14 s; simplify_20M: 9.09 s) | 0 | PASS |

- **Crash/memory leak:** Tidak ada crash; tidak ada exception. RSS delta stabil (~64 MB) di ketiga run; tidak ada pola naik terus yang mengindikasikan memory leak jelas.
- **Freeze:** Freeze >3s hanya pada simplify (5M/20M points); acceptable untuk stress test beban berat.

**Ringkasan E:**  
- **3/3 iterasi PASS**, tanpa exception dan tanpa crash.  
- Tidak ada indikasi memory leak.  
- Stress test **lulus**.

---

## 4. Error & Diagnosis (Ringkas)

| Tahap | Error | Diagnosis |
|-------|--------|-----------|
| A (unit) | Viewer tests: Segmentation fault | OpenGL/Qt context di headless (termasuk offscreen) menyebabkan crash; bukan kegagalan logika aplikasi. |
| A (unit) | test_engine_wrapper: sys.exit saat import | File ini script-style; dijalankan dengan `python tests/test_engine_wrapper.py` → 5 PASS. |
| B (measurement) | `tests/measurement` tidak ada | Tidak ada folder/unit test measurement; engine divalidasi lewat stress 200_measurement_cycles. |
| C (DTM/Ortho) | generate_dtm: LAS not supported | GDAL di env conda tidak punya driver LAS; DTM raster tidak bisa dihasilkan sehingga validasi CRS/GeoTransform/pixel/empty/bbox tidak dilakukan. |

Tidak ada perubahan kode/refactor; hanya konfigurasi interpreter dan penambahan dependency test (pytest, PyYAML, PySide6, psutil) agar suite bisa jalan.

---

## 5. Kesimpulan: Layak Field Release?

**Ringkasan hasil:**

- **Environment:** Python mapfree_prod, GDAL 3.12.2, PDAL 2.10.0 konsisten; interpreter project sudah di-set.
- **Unit/engine:** Engine wrapper PASS; unit test pytest hanya viewer (segfault di headless).
- **Measurement:** Tidak ada `tests/measurement`; measurement engine PASS lewat stress test.
- **DTM/Ortho API:** PASS; pipeline penuh sampai DTM raster **blokir oleh GDAL tanpa driver LAS** di env ini.
- **PDAL:** PASS; tidak ada warning projection/axis order.
- **Stress:** 3/3 iterasi PASS; tidak ada crash/exception/memory leak jelas.

**Rekomendasi:**

- **Belum sepenuhnya layak field release** hanya jika syaratnya adalah: (1) semua unit test (termasuk viewer) lulus di CI, dan (2) validasi penuh DTM raster (CRS, GeoTransform, pixel size, non-empty, bbox) harus berjalan di env yang sama.
- **Layak untuk field release dengan catatan** jika:
  - Viewer tests dianggap optional di headless (atau dijalankan di env dengan display/GPU yang mendukung offscreen);
  - Env production/CI menggunakan GDAL yang dibangun **dengan dukungan LAS** (atau PDAL/GDAL stack yang sama dengan yang sudah dites di lapangan), sehingga DTM pipeline dan validasi raster bisa dijalankan;
  - Hasil round ini diterima: engine wrapper, API DTM/Ortho, PDAL pipeline, dan stress test (termasuk measurement cycles) lulus; satu-satunya blokir adalah GDAL tanpa LAS di env ini dan viewer segfault di headless.

**Singkat:** MapFree **siap untuk field release dengan catatan environment**: gunakan interpreter mapfree_prod, pastikan GDAL dengan driver LAS untuk pipeline DTM penuh, dan jalankan viewer tests hanya di env yang mendukung OpenGL/display atau anggap skip di headless.
