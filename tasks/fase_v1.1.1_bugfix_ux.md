# FASE v1.1.1 — Bug Fix & UX Improvement
# Target: Sebelum Release v1.1.0 | Prasyarat: v1.1 development selesai, CI hijau
# Berdasarkan: Real-world testing dengan 335 foto drone Lewoleba

## TUJUAN
Memperbaiki 5 issue yang ditemukan saat first real-world test MapFree v1.1:
1. Sparse Reconstruction gagal (COLMAP tidak terpanggil)
2. Setup dialog muncul setiap buka app meski dependency sudah terinstall
3. GUI tidak responsive saat maximize/restore
4. Output folder tidak terstruktur rapi
5. Import foto harus bisa pilih file individual (seperti Metashape)

## STATUS LEGEND
# [ ] = Belum mulai
# [~] = Dalam progress
# [x] = Selesai

---

## TASK A — Fix COLMAP Detection & Pipeline
**Priority: KRITIS — Pipeline tidak bisa jalan tanpa ini**

**Cursor Prompt:**
```
Pipeline gagal di Sparse Reconstruction dengan returncode=-1.
COLMAP sudah terinstall tapi tidak terdeteksi saat runtime.

Investigasi dan fix di beberapa file:

1. mapfree/utils/dependency_check.py (dan v2):
   Fungsi yang mencari COLMAP hanya mencari "colmap" di PATH sistem.
   Di Windows, COLMAP bisa berada di:
   - C:\colmap\colmap.exe
   - C:\colmap\bin\colmap.exe  
   - C:\MapFree\deps\colmap\colmap.exe
   - Path dari deps_registry.json

   Fix: buat fungsi find_colmap_executable() yang mencari di:
   a) shutil.which("colmap") — PATH sistem
   b) deps_registry.json — path yang disimpan PathManager
   c) Lokasi default: C:\colmap, C:\colmap\bin, C:\MapFree\deps\colmap
   d) MAPFREE_COLMAP_PATH env var jika ada

2. mapfree/__main__.py atau app.py — urutan startup:
   Pastikan urutan ini:
   a) PathManager().inject_to_env()  ← HARUS sebelum apapun
   b) check_dependencies()
   c) Baru tampilkan GUI

3. mapfree/core/wrapper.py atau colmap_engine.py:
   Saat memanggil COLMAP, gunakan hasil find_colmap_executable()
   bukan hardcode "colmap".
   Tambahkan logging: log full path COLMAP yang dipakai dan
   full command yang dijalankan.

4. Tambahkan di startup log:
   - PATH aktif (os.environ.get("PATH"))
   - Hasil find_colmap_executable() 
   - Versi COLMAP yang ditemukan

Buat tests: tests/utils/test_colmap_finder.py
- test_find_colmap_in_path: mock shutil.which return valid path
- test_find_colmap_in_registry: mock deps_registry.json dengan path COLMAP
- test_find_colmap_in_default_dirs: mock os.path.isfile untuk default dirs
- test_find_colmap_not_found_returns_none

Commit: "fix(pipeline): robust COLMAP executable discovery for Windows"
```

**Checklist:**
- [x] Fungsi find_colmap_executable() dibuat (`mapfree/utils/colmap_finder.py`)
- [x] PathManager.inject_to_env() dipanggil sebelum GUI startup
- [x] COLMAP dipanggil via path eksplisit, bukan hanya nama binary
- [x] Logging path dan command yang dijalankan
- [x] Tests untuk colmap finder (`tests/utils/test_colmap_finder.py`)
- [ ] Pipeline Sparse Reconstruction berhasil di mesin Windows (manual check)

**Commit:** `fix(pipeline): robust COLMAP executable discovery for Windows`

---

## TASK B — Fix Setup Dialog (Skip jika sudah selesai)
**Priority: TINGGI — UX buruk jika muncul setiap buka app**

**Cursor Prompt:**
```
Dialog "Setup Diperlukan" muncul setiap kali MapFree dibuka
meski dependency sudah terinstall sebelumnya.

Fix:

1. Buat file flag: ~/.mapfree/setup_complete.json
   Format:
   {
     "completed": true,
     "checked_at": "2026-03-06T10:00:00",
     "dependencies": {
       "colmap": {"found": true, "path": "C:\\colmap\\colmap.exe", "version": "3.9"},
       "openmvs": {"found": false},
       "pdal": {"found": false},
       "gdal": {"found": false}
     }
   }

2. Di startup flow (sebelum tampilkan dialog):
   a) Load setup_complete.json jika ada
   b) Jika "completed": true DAN colmap.found: true:
      - Skip dialog, langsung ke main window
      - Re-check otomatis jika file berumur > 7 hari
   c) Jika tidak ada file atau colmap.found: false:
      - Tampilkan dialog seperti biasa

3. Saat user klik "Lanjutkan" di dialog:
   - Jalankan check dependency ulang
   - Simpan hasil ke setup_complete.json
   - Jika COLMAP ditemukan: set completed=true, tutup dialog

4. Tambahkan menu: Help → "Periksa Dependency..."
   yang membuka dialog dependency check secara manual.

5. Tambahkan tombol "Refresh / Cek Ulang" di dialog
   untuk trigger re-check tanpa restart app.

Buat/update tests: tests/application/test_setup_state.py
- test_skip_dialog_if_setup_complete
- test_show_dialog_if_no_flag_file
- test_show_dialog_if_colmap_missing
- test_flag_written_after_successful_setup
- test_recheck_after_7_days

Commit: "fix(gui): skip setup dialog if dependencies already verified"
```

**Checklist:**
- [x] setup_complete.json dibuat setelah setup berhasil (Lanjutkan / save_setup_state)
- [x] Dialog di-skip jika file ada dan COLMAP ditemukan (should_skip_dependency_dialog)
- [x] Re-check otomatis setelah 7 hari (recheck_results path)
- [x] Menu Help → Periksa Dependency tersedia (Cek Dependencies…)
- [x] Tombol Refresh di dialog (Cek Ulang)
- [x] Tests untuk logic skip dialog (tests/application/test_setup_state.py)

**Commit:** `fix(gui): skip setup dialog if dependencies already verified`

---

## TASK C — Responsive Layout (Maximize/Restore)
**Priority: MEDIUM**

**Cursor Prompt:**
```
Layout GUI MapFree tidak menyesuaikan saat window di-maximize
atau restore down. Widget tetap ukuran fixed.

Fix di file GUI utama (mapfree/gui/main_window.py atau serupa):

1. Main window layout:
   Gunakan QSplitter horizontal sebagai main container:
   - Left panel: min 220px, max 320px, default 260px
   - Right panel (viewer): expanding, ambil sisa ruang

   splitter = QSplitter(Qt.Horizontal)
   splitter.addWidget(left_panel)
   splitter.addWidget(viewer_panel)
   splitter.setStretchFactor(0, 0)  # left: tidak stretch
   splitter.setStretchFactor(1, 1)  # right: stretch
   splitter.setSizes([260, 900])

2. Left panel:
   - setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
   - setMinimumWidth(220), setMaximumWidth(320)
   - Semua child widget: width = "stretch to parent"

3. Right panel (viewer/map):
   - setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
   - Hapus semua setFixedWidth/setFixedHeight di viewer

4. Toolbar:
   - Gunakan QToolBar dengan setMovable(False)
   - Icon + text, bukan fixed pixel width

5. Status bar bawah:
   - Left: pesan status (expanding)
   - Right: CRS | FPS | Memory | COLMAP status (fixed width per item)

6. Test di:
   - 1920x1080 maximize
   - 1280x720 restore
   - 2560x1440 maximize

Commit: "fix(gui): responsive layout with QSplitter for all window sizes"
```

**Checklist:**
- [x] QSplitter menggantikan fixed layout
- [x] Left panel fixed width, resizable oleh user
- [x] Right panel (viewer) expanding
- [x] Tidak ada hardcoded pixel width/height kecuali yang memang perlu
- [x] Test di 1280x720 dan 1920x1080

**Commit:** `fix(gui): responsive layout with QSplitter for all window sizes`

---

## TASK D — Output Folder Structure (Metashape-style)
**Priority: MEDIUM**

**Cursor Prompt:**
```
Buat struktur output folder yang rapi seperti Metashape.
Saat ini output langsung ke folder yang dipilih user tanpa struktur.

Implementasi di mapfree/core/ atau mapfree/application/:

1. Buat mapfree/core/project_structure.py:

   def create_project_structure(output_dir: Path, project_name: str) -> dict:
       """Buat folder structure dan return dict path."""
       root = output_dir / project_name
       paths = {
           "root": root,
           "sparse": root / "01_sparse",
           "dense": root / "02_dense", 
           "mesh": root / "03_mesh",
           "geospatial": root / "04_geospatial",
           "exports": root / "05_exports",
           "logs": root / "logs",
           "images": root / "images",
       }
       for p in paths.values():
           p.mkdir(parents=True, exist_ok=True)
       
       # Buat project file
       project_file = root / f"{project_name}.mapfree"
       if not project_file.exists():
           project_file.write_text(json.dumps({
               "version": "1.1.1",
               "name": project_name,
               "created": datetime.now().isoformat(),
               "paths": {k: str(v) for k, v in paths.items()}
           }, indent=2))
       
       return paths

2. Struktur folder yang dibuat:
   {output_dir}/{project_name}/
   ├── {project_name}.mapfree   ← file project JSON
   ├── images/                  ← foto sumber (symlink atau copy)
   ├── 01_sparse/               ← COLMAP sparse output
   │   └── 0/
   │       ├── cameras.bin
   │       ├── images.bin
   │       └── points3D.bin
   ├── 02_dense/                ← dense point cloud
   │   └── fused.ply
   ├── 03_mesh/                 ← mesh OpenMVS
   │   ├── mesh.ply
   │   └── mesh_textured.obj
   ├── 04_geospatial/           ← DTM, orthomosaic
   │   ├── dtm.tif
   │   └── orthomosaic.tif
   ├── 05_exports/              ← hasil export user
   └── logs/                    ← semua log file

3. Update pipeline untuk menggunakan paths dari project_structure:
   - COLMAP output → paths["sparse"]
   - Dense output → paths["dense"]
   - Log files → paths["logs"]

4. Di GUI, saat user set Output folder:
   - Field "Job name" menjadi nama subfolder project
   - Preview path ditampilkan: "Output: E:\Output\test_v1.1\"
   - Jika folder sudah ada, tanya: "Project sudah ada, lanjutkan?"

Buat tests: tests/core/test_project_structure.py
- test_creates_all_subfolders
- test_project_file_created
- test_idempotent_on_existing_project
- test_paths_dict_has_all_keys

Commit: "feat(core): Metashape-style project folder structure"
```

**Checklist:**
- [x] create_project_structure() dibuat dan ditest
- [x] Pipeline menggunakan path dari project structure (context + resolve_project_paths)
- [x] Log files masuk ke logs/ subfolder
- [x] GUI menampilkan preview output path (Output: <path>)
- [x] Konfirmasi jika project sudah ada ("Project sudah ada, lanjutkan?")
- [x] Tests untuk project structure (tests/core/test_project_structure.py)

**Commit:** `feat(core): Metashape-style project folder structure`

---

## TASK E — Import Foto: Pilih File Individual (Metashape-style)
**Priority: MEDIUM — UX improvement signifikan**

**Cursor Prompt:**
```
Ganti UX import foto dari "pilih 1 folder" menjadi
"pilih file individual" seperti Metashape.

Implementasi di mapfree/gui/ (panel dataset):

1. Ganti tombol "Select folder..." dengan dua tombol:
   - [Add Photos]   ← buka file picker multi-select
   - [Add Folder]   ← buka folder picker (tetap ada sebagai opsi)

2. QFileDialog multi-select untuk Add Photos:
   files, _ = QFileDialog.getOpenFileNames(
       self,
       "Pilih Foto",
       last_dir,  # ingat direktori terakhir
       "Images (*.jpg *.jpeg *.JPG *.png *.PNG *.tif *.tiff *.TIF *.TIFF)"
   )
   
3. Ganti label "0 images" dengan QListWidget atau panel foto:
   Tampilkan daftar foto dengan info:
   - Nama file
   - Status GPS: ✓ (hijau) jika ada GPS, ✗ (merah) jika tidak
   - Ukuran file (KB/MB)
   
   Di atas list: "335 foto | 330 dengan GPS | 5 tanpa GPS"

4. Tambahkan tombol di bawah list:
   - [Add Photos] [Add Folder] [Remove Selected] [Clear All]

5. Saat foto di-add:
   - Ekstrak GPS dari EXIF di background thread (QThread)
   - Update status GPS per foto saat selesai
   - Tampilkan progress: "Membaca EXIF... 150/335"

6. Saat Run dimulai:
   - Foto dikumpulkan ke project_folder/images/ 
     via symlink (Linux) atau hardlink/copy (Windows)
   - Bukan move, foto asli tetap di lokasi asal

7. Simpan daftar foto ke project.mapfree:
   "images": ["E:/Foto/IMG_001.JPG", "E:/Foto/IMG_002.JPG", ...]

8. Saat buka project lama, restore daftar foto dari project.mapfree

Buat tests: tests/gui/test_photo_import.py (gunakan pytest-qt jika tersedia)
- test_add_photos_populates_list
- test_add_folder_adds_all_images
- test_remove_selected_removes_items
- test_clear_all_empties_list
- test_gps_status_shown_per_photo

Commit: "feat(gui): Metashape-style photo import with file picker and GPS status"
```

**Checklist:**
- [x] Tombol "Add Photos" dengan multi-select file picker
- [x] Tombol "Add Folder" tetap ada
- [x] List foto dengan status GPS per item
- [x] Counter foto: total | dengan GPS | tanpa GPS
- [x] Tombol Remove Selected dan Clear All
- [x] GPS extraction di background thread (GpsExtractWorker)
- [x] Foto dikumpulkan ke images/ subfolder saat Run (copy_or_link_images)
- [x] Daftar foto disimpan di state (images) saat Run
- [x] Restore daftar foto saat buka project (load_state["images"])

**Commit:** `feat(gui): Metashape-style photo import with file picker and GPS status`

---

## CHECKLIST AKHIR v1.1.1 (Sebelum Release)

**Fungsional:**
- [ ] Pipeline berhasil end-to-end dengan 335 foto Lewoleba
- [ ] Feature Extraction → Done ✅
- [ ] Matching → Done ✅
- [ ] Sparse Reconstruction → Done (fix dari TASK A)
- [ ] Dense Reconstruction → Done
- [ ] Output tersimpan rapi di struktur folder (fix dari TASK D)

**UX:**
- [ ] Setup dialog tidak muncul lagi setelah dependency terverifikasi
- [ ] GUI responsive di semua ukuran window
- [ ] Import foto dengan file picker multi-select
- [ ] Output folder terstruktur seperti Metashape

**Release:**
- [ ] CI hijau (develop branch)
- [ ] BoolToStr fix di mapfree_setup.iss sudah di-commit
- [ ] Tag v1.1.0 di-push → GitHub Release otomatis
- [ ] Download installer dari Release, test di mesin bersih
- [ ] Dokumentasi CHANGELOG diupdate

---

## URUTAN PENGERJAAN YANG DISARANKAN

```
TASK A (COLMAP Fix) → Test pipeline → Berhasil?
    ↓ Ya
TASK B (Setup Dialog) → Quick fix, 1-2 jam
    ↓
TASK E (Import Foto) → UX improvement utama
    ↓
TASK D (Output Structure) → Perlu koordinasi dengan pipeline paths
    ↓
TASK C (Responsive Layout) → Polish terakhir
    ↓
Full test ulang dengan 335 foto Lewoleba
    ↓
Release v1.1.0
```

---
*Dibuat: 2026-03-06 | Target selesai: Sebelum release v1.1.0*
