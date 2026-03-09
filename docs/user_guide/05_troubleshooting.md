# 05 — Troubleshooting

Solusi untuk masalah umum saat instalasi dan menjalankan MapFree.

## COLMAP tidak ditemukan

- **Gejala:** dialog dependency checker atau pesan error bahwa COLMAP tidak ditemukan.
- **Solusi:**
  - **Windows:** instal COLMAP dan pastikan executable ada di PATH, atau set path ke COLMAP di **Settings** MapFree (jika ada opsi path). Lihat `scripts/install_colmap_windows.md`.
  - **Linux:** instal paket COLMAP (`sudo apt install colmap` di Ubuntu) atau build dari sumber menggunakan skrip di `scripts/`.
  - Setelah instalasi, restart MapFree. Dependency checker akan mendeteksi COLMAP jika path benar.

## Pipeline crash di tahap mapper

- **Gejala:** pipeline berhenti atau error saat tahap sparse (mapper/ triangulasi).
- **Kemungkinan penyebab:** terlalu sedikit overlap, gambar blur, atau dataset terlalu besar untuk memori.
- **Solusi:**
  - Pastikan overlap antar foto cukup (minimal 3–5 view per titik).
  - Kurangi jumlah gambar per run (gunakan chunk size lebih kecil di config atau `--chunk-size`).
  - Pilih hardware profile **LOW** atau **CPU_SAFE** untuk mengurangi penggunaan memori.
  - Periksa log (panel Console atau `--log-dir`) untuk pesan error spesifik COLMAP.

## Memory out of error

- **Gejala:** proses berhenti dengan pesan out-of-memory (OOM) atau sistem menjadi sangat lambat.
- **Solusi:**
  - Kurangi **chunk size** (jumlah gambar per chunk) di config atau CLI.
  - Gunakan profile **LOW** atau **CPU_SAFE**.
  - Tutup aplikasi lain untuk membebaskan RAM.
  - Untuk dense stage: jika ada opsi VRAM/RAM limit di config, turunkan nilainya.

## OpenGL / 3D viewer tidak muncul

- **Gejala:** jendela 3D viewer tidak terbuka atau crash saat dibuka.
- **Solusi:**
  - Pastikan driver GPU dan OpenGL up to date. Di Linux, coba jalankan dengan software OpenGL: `QT_OPENGL=software mapfree gui` (atau set variabel ini sebelum menjalankan).
  - Jika tersedia, aktifkan opsi fallback viewer (non-OpenGL) di Settings.
  - Di lingkungan headless/SSH, 3D viewer membutuhkan virtual display (Xvfb) atau akses ke display.

## DTM / orthophoto tidak dihasilkan

- **Gejala:** pipeline selesai tetapi tidak ada file orthophoto atau DTM di folder `geospatial/`.
- **Kemungkinan penyebab:** tahap geospatial belum dijalankan, dependency (mis. GDAL/PDAL) tidak terpasang, atau konfigurasi menonaktifkan ekspor.
- **Solusi:**
  - Pastikan pipeline menjalankan tahap geospatial (lihat config dan dokumentasi engine).
  - Periksa dependency checker untuk GDAL/PDAL; instal jika diperlukan.
  - Periksa path output dan izin tulis pada folder project. Lihat log untuk error saat menulis GeoTIFF.

---

Untuk panduan instalasi dan persyaratan sistem, kembali ke [01 — Instalasi](01_instalasi.md).
