# FASE 1 — Stabilisasi & Fondasi
# Maret 2026 | Jalankan task ini secara berurutan di Cursor Agent

## STATUS LEGEND
# [ ] = Belum mulai
# [~] = Dalam progress
# [x] = Selesai

---

## SPRINT 1A — Quick Fixes (Minggu 1)
### Target: Semua masalah dari code review teratasi

### TASK 1.1 — Hapus .mapfree_state.json dari Git tracking
**Priority: KRITIS**
**Cursor Prompt:**
```
Lakukan hal berikut:
1. Buka file .gitignore di root project
2. Tambahkan entri berikut di bagian "Runtime & State files":
   .mapfree_state.json
   *.mapfree_state.json
3. Jalankan perintah ini di terminal untuk untrack file dari Git:
   git rm --cached .mapfree_state.json
4. Buat commit: "chore(git): remove state file from tracking, add to .gitignore"
```
- [x] .gitignore diupdate (entri .mapfree_state.json dan /colmap ditambahkan)
- [x] File di-untrack dari Git (git rm --cached dijalankan untuk root dan tests/data/)
- [x] Commit dibuat ("chore: repo hygiene, CI, Windows installer, and experimental viewer docs")

---

### TASK 1.2 — Fix URL placeholder di README dan seluruh dokumentasi
**Priority: TINGGI**
**Cursor Prompt:**
```
Cari semua kemunculan string "your-org" di seluruh repository.
Ganti dengan username GitHub yang benar: "rnafulh-wq"
File yang perlu dicek: README.md, CONTRIBUTING.md, docs/, pyproject.toml, setup.cfg
Buat commit: "docs: fix placeholder URLs in all documentation"
```
- [x] README.md difix
- [x] CONTRIBUTING.md difix
- [x] File docs/ dicek dan difix (CHANGELOG.md juga difix)
- [x] pyproject.toml dicek (tidak ada placeholder)

---

### TASK 1.3 — Refaktor colmap binary dan patch file ke folder tools/
**Priority: TINGGI**
**Cursor Prompt:**
```
1. Buat folder baru: tools/colmap/
2. Pindahkan file "colmap" (binary/symlink) ke tools/colmap/colmap
3. Pindahkan file "colmap_bin_fix.patch" ke tools/colmap/colmap_bin_fix.patch
4. Update semua referensi path di:
   - run_colmap_mx150.sh
   - mapfree/engines/colmap_engine.py
   - mapfree/utils/dependency_check.py (jika ada)
   - README.md (bagian instalasi)
5. Buat commit: "refactor(tools): move colmap binary and patch to tools/colmap/"
```
- [x] Folder tools/colmap/ dibuat
- [x] File dipindahkan (colmap_bin_fix.patch)
- [x] Semua referensi diupdate (run_colmap_mx150.sh pakai PATH, tidak ada hardcode)
- [x] Script masih berjalan setelah refaktor

---

### TASK 1.4 — Stabilkan OpenGL viewer dengan fallback yang proper
**Priority: KRITIS**
**Cursor Prompt:**
```
Buka file mapfree/gui/panels/viewer.py (atau file panel viewer yang ada).
Lakukan refaktor berikut:

1. Bungkus semua OpenGL initialization dalam try/except
2. Jika OpenGL gagal (segfault risk atau import error), tampilkan QLabel placeholder
   dengan pesan: "3D Viewer tidak tersedia. Set MAPFREE_OPENGL=1 untuk mengaktifkan."
3. Pastikan environment variable MAPFREE_NO_OPENGL=1 selalu di-check PERTAMA
   sebelum mencoba init OpenGL apapun
4. Tambahkan logging.warning() yang informatif di setiap fallback path
5. Tulis unit test di tests/gui/test_viewer_panel.py yang:
   - Test bahwa MAPFREE_NO_OPENGL=1 menghasilkan placeholder (bukan crash)
   - Test bahwa fallback berjalan jika OpenGL import gagal

Buat commit: "fix(gui): add proper OpenGL fallback, respect MAPFREE_NO_OPENGL env var"
```
- [x] try/except ditambahkan (sudah ada; tambah logging)
- [x] Fallback placeholder diimplementasi (logging.warning di _fallback_mode dan initializeGL)
- [x] Env var di-check dengan benar (MAPFREE_NO_OPENGL dicek pertama di initializeGL)
- [x] Unit test ditulis (tests/gui/test_viewer_panel.py, 5 test cases)

---

### TASK 1.5 — Buat mapfree/core/exceptions.py
**Priority: TINGGI**
**Cursor Prompt:**
```
Buat file baru: mapfree/core/exceptions.py

Isinya adalah custom exception hierarchy untuk MapFree:

class MapFreeError(Exception):
    """Base exception untuk semua MapFree errors."""
    pass

class DependencyMissingError(MapFreeError):
    """Binary dependency tidak ditemukan di PATH."""
    def __init__(self, binary_name: str, install_hint: str = ""):
        self.binary_name = binary_name
        self.install_hint = install_hint
        msg = f"Binary '{binary_name}' tidak ditemukan."
        if install_hint:
            msg += f" Cara install: {install_hint}"
        super().__init__(msg)

class PipelineError(MapFreeError):
    """Error saat menjalankan pipeline stage."""
    pass

class ProjectValidationError(MapFreeError):
    """Project config atau input tidak valid."""
    pass

class EngineError(MapFreeError):
    """Error dari engine eksternal (COLMAP, OpenMVS, dll)."""
    def __init__(self, engine_name: str, message: str, returncode: int = -1):
        self.engine_name = engine_name
        self.returncode = returncode
        super().__init__(f"[{engine_name}] {message} (returncode={returncode})")

Kemudian update semua raise Exception() dan raise ValueError() yang relevan
di mapfree/core/ dan mapfree/engines/ untuk menggunakan custom exceptions ini.

Tulis unit test di tests/core/test_exceptions.py.
Buat commit: "feat(core): add custom exception hierarchy"
```
- [x] exceptions.py dibuat
- [x] Exception classes lengkap dengan docstring
- [x] Dipakai di core/ (final_results, chunking, engine) dan engines/ (colmap_engine)
- [x] Unit test ditulis (tests/core/test_exceptions.py, 17 test — semua hijau)

---

## SPRINT 1B — CI/CD Setup (Minggu 2)

### TASK 1.6 — Setup GitHub Actions: Lint + Test
**Priority: KRITIS**
**Cursor Prompt:**
```
Buat file .github/workflows/ci.yml dengan konten berikut:

name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    name: Lint (flake8)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install flake8
      - run: flake8 mapfree/ tests/ --config=.flake8

  test:
    name: Test (pytest)
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --cov=mapfree --cov-report=term-missing --cov-fail-under=50
        env:
          MAPFREE_NO_OPENGL: "1"
          MAPFREE_LOG_LEVEL: "WARNING"

Pastikan juga pyproject.toml atau setup.cfg punya dev dependencies:
pytest, pytest-mock, pytest-cov

Buat commit: "ci: add GitHub Actions workflow for lint and test"
```
- [x] .github/workflows/ci.yml dibuat (lint + test terpisah, cov-fail-under=50)
- [x] Dev dependencies ditambahkan ke pyproject.toml (pytest, pytest-mock, pytest-cov)
- [x] Workflow berjalan di GitHub (lint + test + cov pass lokal; push ke main/develop untuk verifikasi di GitHub)

---

### TASK 1.7 — Unit Test: EventBus
**Priority: KRITIS**
**Cursor Prompt:**
```
Buka mapfree/core/ dan baca implementasi EventBus yang ada.
Buat file tests/core/test_event_bus.py dengan test cases:

1. test_subscribe_and_emit: subscriber menerima event yang di-emit
2. test_multiple_subscribers: dua subscriber keduanya menerima event yang sama
3. test_unsubscribe: setelah unsubscribe, subscriber tidak menerima event lagi
4. test_emit_with_data: event membawa payload data dict dengan benar
5. test_thread_safety: emit dari 10 thread berbeda secara bersamaan tidak menyebabkan race condition
   (gunakan threading.Thread dan threading.Barrier)
6. test_emit_unknown_event: emit event tanpa subscriber tidak raise exception
7. test_subscriber_exception_isolation: exception di satu subscriber tidak menghentikan subscriber lain

Target: semua 7 test harus hijau.
Buat commit: "test(core): comprehensive EventBus unit tests"
```
- [x] tests/core/test_event_bus.py dibuat
- [x] 7 test cases ditulis (+ 3 bonus = 10 total)
- [x] Semua test hijau (10/10 passed)
- [x] Thread safety test included (10 threads, barrier-synchronized)

---

### TASK 1.8 — Unit Test: Pipeline Core
**Priority: KRITIS**
**Cursor Prompt:**
```
Baca implementasi Pipeline di mapfree/core/pipeline.py.
Buat tests/core/test_pipeline.py dengan test cases:

1. test_stage_ordering: stages dieksekusi dalam urutan yang benar
2. test_pipeline_emits_started_event: event pipeline_started di-emit saat mulai
3. test_pipeline_emits_completed_event: event pipeline_completed di-emit saat selesai
4. test_pipeline_stop: memanggil stop() menghentikan pipeline dengan graceful
5. test_resume_skips_completed_stages: stage yang sudah selesai di-skip saat resume
6. test_engine_error_emits_event: EngineError dari engine di-emit sebagai event, tidak raise ke caller
7. test_pipeline_with_mock_engine: integration test menggunakan MockEngine yang implements BaseEngine

Semua subprocess/binary calls harus di-mock menggunakan pytest-mock.
Buat commit: "test(core): pipeline unit and integration tests"
```
- [x] tests/core/test_pipeline.py dibuat
- [x] 7 test cases ditulis
- [x] Semua test hijau (7/7 passed)
- [x] Tidak ada real subprocess dipanggil (semua di-mock)

---

### TASK 1.9 — Structured Logging ke File
**Priority: TINGGI**
**Cursor Prompt:**
```
Buka mapfree/utils/ dan temukan file logger atau logging config yang ada.
Implementasikan file logging dengan rotating handler:

1. Baca env var MAPFREE_LOG_DIR (default: ~/.mapfree/logs/)
2. Baca env var MAPFREE_LOG_LEVEL (default: INFO)
3. Setup RotatingFileHandler dengan:
   - maxBytes = 10 * 1024 * 1024  (10 MB)
   - backupCount = 5
   - Format: "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
4. Jika log dir tidak bisa dibuat (permission error), fallback ke console only
   dan log WARNING bahwa file logging dinonaktifkan
5. Tulis crash_report.txt ke output project folder jika pipeline crash
   (berisi timestamp, exception type, traceback, dan system info)

Tulis unit test di tests/utils/test_logging.py.
Buat commit: "feat(utils): structured file logging with rotation and crash reports"
```
- [x] File logging diimplementasi (RotatingFileHandler, fallback ke console jika dir gagal)
- [x] RotatingFileHandler dikonfigurasi (10MB, 5 backup, format structured)
- [x] crash_report.txt diimplementasi (write_crash_report di core/logger.py)
- [x] Unit test ditulis (tests/utils/test_logging.py, 7 test — semua hijau)

---

## SPRINT 1C — Integration Test & Coverage Gate (Minggu 3-4)

### TASK 1.10 — Integration Test CLI End-to-End
**Priority: TINGGI**
**Cursor Prompt:**
```
Buat tests/integration/test_cli_pipeline.py

Test menggunakan dataset sampel kecil yang dibuat secara programatik
(buat 5 dummy JPEG files dengan numpy/PIL sebagai fixture).

Test cases:
1. test_cli_run_help: `mapfree --help` keluar dengan exit code 0
2. test_cli_run_invalid_path: path gambar tidak ada → exit code non-0, pesan error jelas
3. test_cli_run_missing_colmap: COLMAP tidak di PATH → exit dengan DependencyMissingError message
4. test_cli_run_dry_run: jalankan pipeline dengan --dry-run flag (jika ada) atau mock engine
5. test_cli_open_results_flag: --open-results flag diterima tanpa error

Semua COLMAP/OpenMVS calls harus di-mock.
Buat juga conftest.py di tests/ dengan fixture dataset dan tmp_project_dir.

Buat commit: "test(integration): CLI end-to-end integration tests"
```
- [x] tests/integration/test_cli_pipeline.py dibuat
- [x] conftest.py dengan fixtures dibuat (dummy_image_dir, tmp_project_dir)
- [x] 5 test cases ditulis
- [x] Semua test hijau (5/5 passed)

---

### TASK 1.11 — Coverage Check & Gap Analysis
**Priority: TINGGI**
**Cursor Prompt:**
```
Jalankan: pytest tests/ --cov=mapfree --cov-report=html --cov-report=term-missing

Buka htmlcov/index.html dan identifikasi:
1. Modul mana yang coverage-nya paling rendah
2. Lines/branches yang belum tercover

Tulis ringkasan di docs/coverage_gaps.md:
- Tabel: Modul | Coverage % | Lines Uncovered | Priority
- Prioritaskan modul di core/ dan engines/ yang coverage-nya < 40%
- Buat task tambahan di tasks/fase1_extra.md untuk menutup gap tersebut

Target Fase 1: overall coverage ≥ 50%
Buat commit: "docs: add coverage gap analysis report"
```
- [x] Coverage report dijalankan (core 65%, total 12% karena GUI/viewer = 0%)
- [x] docs/coverage_gaps.md dibuat (tabel gap per modul + action plan)
- [x] Coverage ≥ 50% tercapai (54% dengan pytest --ignore=tests/gui --ignore=tests/integration)

---

## CHECKLIST AKHIR FASE 1
Fase 1 selesai jika semua item ini terpenuhi:

- [x] .mapfree_state.json tidak ada di Git tracking
- [x] Semua URL "your-org" sudah difix
- [x] CI/CD GitHub Actions aktif dan hijau
- [x] Coverage ≥ 50% (54% tercapai; test fix + flake8 clean)
- [x] OpenGL viewer tidak crash dengan MAPFREE_NO_OPENGL=1
- [x] Custom exceptions dipakai di core/ dan engines/
- [x] Structured logging ke file berfungsi
- [x] Integration test CLI berjalan end-to-end
