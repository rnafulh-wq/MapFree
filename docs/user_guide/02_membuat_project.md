# 02 — Membuat project

Cara menyiapkan foto, membuka MapFree GUI, dan memilih folder gambar serta output.

## Persiapan foto

- **Overlap:** pastikan setiap objek terlihat di minimal 3–5 foto dari sudut berbeda. Overlap 60–80% antar foto berurutan disarankan.
- **Pencahayaan:** hindari bayangan keras dan perubahan lighting ekstrem. Foto indoor/outdoor konsisten memberikan hasil lebih baik.
- **Format:** JPEG atau PNG. Nama file bebas; urutan tidak harus rapi.
- **Resolusi:** 2–12 MP per foto umumnya cukup. Resolusi sangat besar memperlambat pipeline dan membutuhkan RAM lebih banyak.

## Membuka MapFree GUI

- **Windows (installer):** jalankan `MapFree.exe` dari folder hasil ekstrak `MapFree-windows.zip`.
- **Windows/Linux (pip):** di terminal jalankan:
  ```bash
  mapfree gui
  ```
- **Linux (AppImage):** jalankan `./MapFree-x86_64.AppImage`.

Jendela utama menampilkan panel Project, Console/Progress, dan Viewer. Jika dependency (mis. COLMAP) belum terdeteksi, dialog akan muncul dengan petunjuk instalasi.

## Memilih folder gambar dan output

1. Di panel **Project**, gunakan kontrol untuk memilih **folder gambar** (berisi file foto).
2. Pilih atau ketik **folder output (project path)**. Semua hasil pipeline (sparse, dense, geospatial) akan disimpan di sini.
3. Pastikan path tidak berisi karakter khusus (spasi boleh). Hindari path yang terlalu panjang di Windows.

Setelah folder gambar dan output ditetapkan, Anda bisa menjalankan pipeline (lihat [03 — Menjalankan pipeline](03_menjalankan_pipeline.md)).
