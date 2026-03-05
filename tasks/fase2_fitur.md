# FASE 2 — Fitur & Kualitas
# April 2026 | Prasyarat: semua checklist Fase 1 sudah [x]

## STATUS LEGEND
# [ ] = Belum mulai
# [~] = Dalam progress
# [x] = Selesai

---

## SPRINT 2A — 3D Viewer (Minggu 5-6)

### TASK 2.1 — Point Cloud Viewer dengan PyQtGraph
**Priority: KRITIS**
**Cursor Prompt:**
```
Tambahkan pyqtgraph ke requirements.txt dan pyproject.toml.

Buat mapfree/gui/panels/viewer_3d.py dengan class PointCloudViewer(QWidget):

Implementasi:
1. Load file PLY menggunakan numpy (baca header PLY, parse vertex x/y/z dan color rgb)
2. Render point cloud menggunakan pyqtgraph.opengl.GLScatterPlotItem
3. Orbit camera dengan mouse drag (kiri = rotate, tengah = pan, scroll = zoom)
4. Tombol "Reset View" yang center kamera ke centroid point cloud
5. Tampilkan jumlah titik di status bar: "X,XXX,XXX points loaded"
6. Fallback graceful jika pyqtgraph tidak tersedia (tampilkan placeholder label)

Integrasikan ke mapfree/gui/panels/viewer.py sebagai tab atau swap widget.

Tulis tests/gui/test_viewer_3d.py:
- test_load_ply_valid: load PLY dummy, verifikasi point count benar
- test_load_ply_invalid: file tidak ada atau corrupt → error message, tidak crash
- test_viewer_no_opengl: MAPFREE_NO_OPENGL=1 → placeholder, tidak crash

Buat commit: "feat(gui): implement point cloud viewer with PyQtGraph"
```
- [x] pyqtgraph ditambahkan ke dependencies
- [x] PointCloudViewer class dibuat
- [x] PLY parser diimplementasi
- [x] Kontrol kamera berfungsi
- [x] Fallback berjalan
- [x] Unit test ditulis

---

### TASK 2.2 — Mesh Viewer (OBJ/PLY dengan shading)
**Priority: TINGGI**
**Cursor Prompt:**
```
Extend mapfree/gui/panels/viewer_3d.py dengan class MeshViewer(QWidget):

Implementasi menggunakan pyqtgraph.opengl:
1. Load OBJ atau PLY mesh (vertices + faces)
2. Render dengan GLMeshItem menggunakan smooth=True dan drawEdges=False
3. Phong shading sederhana (ambient + diffuse)
4. Toggle wireframe dengan shortcut key 'W'
5. Toggle shading mode: solid/wireframe/points dengan toolbar button
6. Load progress dialog jika mesh > 100k faces (loading bisa lama)

Integrasikan sebagai tab kedua di viewer panel (tab "Sparse" dan tab "Dense").

Buat commit: "feat(gui): add mesh viewer with shading and wireframe toggle"
```
- [x] MeshViewer class dibuat
- [x] OBJ loader diimplementasi
- [x] Shading berfungsi
- [x] Wireframe toggle berfungsi
- [x] Tab integration selesai

---

### TASK 2.3 — Live Preview (stream point cloud sambil pipeline berjalan)
**Priority: SEDANG**
**Cursor Prompt:**
```
Implementasikan live preview point cloud saat sparse reconstruction berjalan:

1. Di colmap_engine.py, setelah setiap mapper iteration selesai, emit event
   "sparse_checkpoint" dengan path ke sparse/0/points3D.bin (COLMAP binary format)

2. Buat parser untuk COLMAP points3D.bin di mapfree/utils/colmap_io.py:
   - Baca format binary COLMAP (dokumentasi ada di colmap.github.io)
   - Return numpy array shape (N, 6): x, y, z, r, g, b

3. Di QtController, subscribe ke "sparse_checkpoint" event dan emit Qt signal
   ke viewer untuk refresh point cloud

4. PointCloudViewer: tambahkan method refresh_points(xyz_rgb: np.ndarray)
   yang update render tanpa reload seluruh widget

Buat commit: "feat(pipeline): live point cloud preview during sparse reconstruction"
```
- [x] sparse_checkpoint event di-emit dari engine
- [x] colmap_io.py dengan binary parser dibuat
- [x] Qt signal chain tersambung
- [x] Viewer refresh tanpa flicker

---

## SPRINT 2B — Sistem Lisensi (Minggu 6-7)

### TASK 2.4 — Offline License Validation
**Priority: KRITIS**
**Cursor Prompt:**
```
Implementasikan sistem lisensi offline di mapfree/application/license_manager.py
(file ini saat ini masih stub — isi dengan implementasi nyata).

Desain:
1. License key format: XXXX-XXXX-XXXX-XXXX (16 hex chars, dash sebagai separator)
2. Validasi dengan HMAC-SHA256:
   - Key = MAPFREE_LICENSE_SECRET (env var, hardcode default untuk dev)
   - Message = f"{license_key}:{machine_id}"
   - machine_id = hash dari MAC address + CPU info (pakai platform + uuid modules)
   - Simpan hasil validasi di cache ~/.mapfree/license.json
3. Method yang dibutuhkan:
   - validate(key: str) -> LicenseStatus (VALID, INVALID, EXPIRED, TRIAL)
   - get_expiry_date(key: str) -> datetime | None
   - is_feature_enabled(feature: str) -> bool
   - get_machine_id() -> str
4. Trial mode: jika tidak ada key, cek ~/.mapfree/trial.json untuk tanggal pertama launch
   Trial berlaku 30 hari, setelah itu is_feature_enabled("premium") return False

Tulis tests/application/test_license_manager.py (mock MAPFREE_LICENSE_SECRET)
Buat commit: "feat(application): implement offline license validation with HMAC"
```
- [x] license_manager.py diimplementasi (bukan stub)
- [x] HMAC validation berfungsi
- [x] Trial mode 30 hari berfungsi
- [x] machine_id generation stabil antar restart
- [x] Unit test ditulis (dengan mocked secret)

---

### TASK 2.5 — License Dialog UI
**Priority: TINGGI**
**Cursor Prompt:**
```
Buka mapfree/gui/dialogs/ dan implementasikan LicenseDialog yang sebelumnya masih stub.

UI Elements:
1. QLineEdit untuk input license key (format auto: XXXX-XXXX-XXXX-XXXX)
   - Auto-insert dash setiap 4 karakter saat user mengetik
   - Konversi ke uppercase otomatis
2. QPushButton "Aktivasi" yang trigger license_manager.validate()
3. QLabel status: "✓ Lisensi Valid" (hijau) / "✗ Key tidak valid" (merah) / "Trial (X hari tersisa)"
4. QLabel machine_id (kecil, gray): "Machine ID: XXXX" untuk keperluan support
5. QPushButton "Beli Lisensi" yang buka URL website (placeholder URL dulu)

Connect dialog ke MainWindow:
- Buka dari menu Help → Aktivasi Lisensi
- Jika trial expired, tampilkan dialog otomatis saat startup (non-blocking)

Buat commit: "feat(gui): implement license activation dialog"
```
- [x] LicenseDialog UI lengkap
- [x] Auto-format key input
- [x] Status indicator berfungsi
- [x] Terintegrasi ke MainWindow menu
- [x] Trial expired dialog saat startup

---

## SPRINT 2C — Installer & UX (Minggu 7-8)

### TASK 2.6 — Dependency Checker di Startup
**Priority: KRITIS**
**Cursor Prompt:**
```
Buka mapfree/utils/dependency_check.py dan implementasikan dependency checker
yang dijalankan saat aplikasi pertama kali dibuka.

Implementasi:
1. check_all_dependencies() -> dict[str, DependencyStatus]
   Cek: colmap, openMVS (DensifyPointCloud, ReconstructMesh, TextureMesh),
        pdal (opsional), gdalinfo (opsional)

2. DependencyStatus: dataclass dengan field:
   - available: bool
   - version: str | None
   - path: str | None
   - install_hint: str

3. Di mapfree/gui/main_window.py, panggil check_all_dependencies() saat startup
   (di QTimer.singleShot(0, ...) agar tidak blocking)
   Jika ada dependency KRITIS yang hilang (colmap), tampilkan QDialog:
   - Judul: "Setup Diperlukan"
   - Tabel dependency: Nama | Status | Versi | Cara Install
   - Tombol "Buka Panduan Instalasi" (buka README di browser)
   - Tombol "Lanjutkan Tanpa X" (disable fitur yang membutuhkan binary hilang)

4. Simpan hasil check ke ~/.mapfree/dependency_cache.json dengan TTL 1 jam
   (tidak perlu cek ulang setiap launch)

Buat commit: "feat(gui): startup dependency checker with actionable install hints"
```
- [x] check_all_dependencies() diimplementasi
- [x] DependencyStatus dataclass dibuat
- [x] Startup dialog UI selesai
- [x] Cache dependency check (1 jam TTL)
- [x] Unit test untuk checker

---

### TASK 2.7 — Installer Script Windows (PowerShell)
**Priority: KRITIS**
**Cursor Prompt:**
```
Buat scripts/install_windows.ps1 — installer script untuk Windows.

Script harus:
1. Cek apakah dijalankan sebagai Administrator (jika tidak, minta elevasi)
2. Install Chocolatey jika belum ada
3. Install COLMAP via: choco install colmap -y
   Jika gagal, unduh installer COLMAP dari GitHub Releases dan jalankan silent install
4. Install Python 3.10+ jika belum ada
5. Install MapFree: pip install -e . (atau dari wheel jika tersedia)
6. Verifikasi instalasi: jalankan `mapfree --version`
7. Buat shortcut di Desktop untuk `mapfree gui`
8. Tampilkan pesan sukses dengan instruksi next steps

Juga update README.md bagian instalasi dengan instruksi Windows:
```powershell
# Jalankan di PowerShell sebagai Administrator
Set-ExecutionPolicy Bypass -Scope Process -Force
.\scripts\install_windows.ps1
```

Buat commit: "feat(scripts): add Windows PowerShell installer script"
```
- [x] install_windows.ps1 dibuat
- [x] Chocolatey install logic selesai
- [x] COLMAP install logic selesai
- [x] Desktop shortcut dibuat
- [x] README diupdate

---

### TASK 2.8 — Project History Panel & Settings Dialog
**Priority: TINGGI**
**Cursor Prompt:**
```
BAGIAN A — Project History:
Buka mapfree/gui/panels/ dan buat ProjectHistoryPanel atau tambahkan ke project panel yang ada.

Fitur:
1. Simpan daftar 10 project terakhir di ~/.mapfree/recent_projects.json
   Format: [{path, name, last_opened, status: completed|in_progress|failed, thumbnail}]
2. Tampilkan sebagai QListWidget dengan item custom:
   - Nama project (bold)
   - Path (kecil, gray)  
   - Status badge berwarna
   - Tombol "Resume" (jika status in_progress) atau "Buka Output" (jika completed)
3. Klik kanan → "Hapus dari history" atau "Buka di File Explorer"

BAGIAN B — Settings Dialog:
Buat mapfree/gui/dialogs/settings_dialog.py dengan tab:

Tab "Paths":
- COLMAP binary path (QLineEdit + Browse button)
- OpenMVS binary dir (QLineEdit + Browse button)  
- Default output directory

Tab "Hardware":
- Hardware profile dropdown: Auto-detect | Low (≤4GB VRAM) | Medium | High
- Max RAM usage slider (GB)
- GPU selection jika multi-GPU

Tab "Pipeline":
- Toggle enable_geospatial
- Toggle chunking otomatis
- Max chunk size (images)

Simpan settings ke ~/.mapfree/config.yaml, load saat startup.
Buat commit: "feat(gui): project history panel and settings dialog"
```
- [x] recent_projects.json persistence selesai
- [x] Project history panel UI selesai
- [x] Resume/Buka Output action berfungsi
- [x] Settings dialog dengan 3 tab selesai
- [x] Settings tersimpan dan ter-load saat startup

---

## CHECKLIST AKHIR FASE 2

- [x] 3D viewer bisa render point cloud PLY dari hasil COLMAP
- [x] Mesh viewer berfungsi dengan OBJ/PLY
- [x] Lisensi offline: validasi, trial 30 hari, feature gating
- [x] License dialog UI berfungsi dan terintegrasi ke menu
- [x] Dependency checker aktif di startup dengan dialog informatif
- [x] Installer Windows (PowerShell) tersedia dan teruji
- [x] Project history panel berfungsi
- [x] Settings dialog tersimpan ke config
- [x] Coverage masih ≥ 55% setelah penambahan fitur baru (55% tercapai, CI cov-fail-under=55)
