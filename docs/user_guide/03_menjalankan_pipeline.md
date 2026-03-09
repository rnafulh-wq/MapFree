# 03 — Menjalankan pipeline

Cara menjalankan pipeline, memilih hardware profile, memantau progress, serta menghentikan dan melanjutkan.

## Overview tahapan

Pipeline MapFree berjalan dalam tahap berurutan:

1. **Sparse reconstruction** — ekstraksi fitur, matching, dan triangulasi (COLMAP). Hasil: point cloud sparse dan kamera.
2. **Dense reconstruction** — densifikasi point cloud (opsional, tergantung engine). Hasil: point cloud padat.
3. **Geospatial** — ekspor DTM/orthophoto dan format lain (jika didukung oleh konfigurasi).

Setiap tahap menulis ke subfolder di project path: `sparse/`, `dense/`, `geospatial/`.

## Memilih hardware profile

- Di **GUI:** buka **Settings** (menu atau tombol pengaturan). Pilih **Hardware profile**: LOW, MEDIUM, HIGH, atau CPU_SAFE. Profile mempengaruhi ukuran chunk dan penggunaan RAM/GPU.
- Di **CLI:** gunakan `--force-profile`:
  ```bash
  mapfree run /path/to/images -o /path/to/project --force-profile MEDIUM
  ```
  Pilihan: `LOW`, `MEDIUM`, `HIGH`, `CPU_SAFE`. Jika tidak diset, profile dipilih otomatis berdasarkan hardware.

## Memantau progress dan log

- **GUI:** panel **Progress** / **Console** menampilkan pesan tahap dan persentase. Log juga ditulis ke file jika **Settings** mengatur direktori log.
- **CLI:** progress dan log tampil di terminal. Gunakan `--log-dir /path/to/logs` untuk menyimpan log ke file, dan `--log-level DEBUG` untuk detail lebih banyak.

## Menghentikan dan melanjutkan pipeline

- **Stop:** di GUI gunakan tombol **Stop** (atau setara). Pipeline akan berhenti dengan graceful; hasil tahap yang sudah selesai tetap tersimpan.
- **Resume:** jalankan ulang pipeline dengan **project path** yang sama. MapFree memanfaatkan hasil yang sudah ada (mis. sparse) dan melanjutkan dari tahap yang belum selesai, sesuai logika aplikasi.

Setelah pipeline selesai, Anda dapat membuka 3D viewer dan hasil (lihat [04 — Melihat hasil](04_melihat_hasil.md)).
