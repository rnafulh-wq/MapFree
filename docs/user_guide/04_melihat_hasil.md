# 04 — Melihat hasil

Cara membuka 3D viewer, menavigasi point cloud dan mesh, serta menggunakan opsi CLI dan struktur output.

## Membuka 3D viewer

- **GUI:** setelah pipeline selesai (atau saat ada checkpoint sparse), gunakan tombol/panel **3D Viewer** (atau **Viewer**) untuk membuka jendela point cloud. Jika mesh tersedia, pilih tampilan mesh di viewer yang sama.
- **Checkpoint sparse:** jika pipeline sudah menghasilkan sparse reconstruction, viewer dapat menampilkan point cloud dari checkpoint tersebut tanpa menunggu pipeline selesai penuh.

## Navigasi point cloud dan mesh

- **Rotasi / pan / zoom:** gunakan kontrol di jendela 3D (biasanya drag untuk rotasi, scroll untuk zoom, shift+drag untuk pan). Detail tergantung implementasi viewer (PyQtGraph/OpenGL).
- **Toggle mesh:** jika viewer mendukung mesh, gunakan opsi **shading** atau **wireframe** untuk mengalihkan tampilan antara permukaan dan wireframe.
- **Point cloud vs mesh:** pilih layer atau sumber data (sparse/dense point cloud atau mesh) dari panel viewer jika tersedia.

## Menggunakan --open-results di CLI

Setelah pipeline selesai dari CLI, Anda dapat membuka folder output dan file hasil di aplikasi default sistem:

```bash
mapfree run /path/to/images -o /path/to/project --open-results
```

Dengan `--open-results`:
- Folder **project path** akan dibuka di file manager.
- Jika ada, file **orthophoto** dan **DTM** (di subfolder geospatial) akan dibuka di aplikasi default (viewer gambar/GIS).

Berguna untuk pemeriksaan cepat tanpa membuka GUI.

## Format output: sparse/, dense/, geospatial/

Struktur folder project setelah pipeline:

- **sparse/** — hasil COLMAP sparse reconstruction: point cloud (mis. `points3D.bin` / `.txt`), kamera, dan gambar. Ini dasar untuk dense dan geospatial.
- **dense/** — point cloud padat dan mesh (jika tahap dense dijalankan). Format tergantung engine (mis. COLMAP/OpenMVS).
- **geospatial/** — hasil yang siap untuk GIS: orthophoto (GeoTIFF), DTM, dan turunan lain. Nama file mengikuti konfigurasi (mis. `orthophoto.tif`, `dtm.tif`).

Semua path relatif terhadap **project path** yang Anda pilih saat membuat project.
