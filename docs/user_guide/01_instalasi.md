# 01 — Instalasi

Panduan instalasi MapFree di Windows dan Linux.

## Persyaratan sistem

- **RAM:** Minimal 8 GB; disarankan 16 GB atau lebih untuk dataset besar.
- **GPU:** Opsional. Pipeline COLMAP dapat berjalan di CPU; GPU mempercepat feature extraction dan matching.
- **OS:** Windows 10/11 (64-bit) atau Linux (Ubuntu 22.04+ disarankan).
- **Storage:** Ruang cukup untuk folder project (sparse, dense, geospatial). Siapkan 2–5× ukuran foto untuk output.

## Instalasi Windows

1. Pasang **Python 3.10+** dari [python.org](https://www.python.org/downloads/). Centang "Add Python to PATH".
2. Pasang **COLMAP** dan (opsional) **OpenMVS**. Lihat `scripts/install_colmap_windows.md` untuk panduan.
3. Install MapFree:
   - Dari sumber: clone repo lalu `pip install -e .`
   - Atau gunakan skrip instalasi: jalankan **PowerShell as Administrator** dan eksekusi:
     ```powershell
     Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
     .\scripts\install_windows.ps1
     ```
4. **Installer siap pakai:** unduh `MapFree-windows.zip` dari [GitHub Releases](https://github.com/rnafulh-wq/MapFree/releases), ekstrak, lalu jalankan `MapFree.exe` di dalam folder `MapFree`. Tidak perlu Python.

## Instalasi Linux

- **AppImage (disarankan):** unduh `MapFree-x86_64.AppImage` dari [GitHub Releases](https://github.com/rnafulh-wq/MapFree/releases). Beri izin eksekusi dan jalankan:
  ```bash
  chmod +x MapFree-x86_64.AppImage
  ./MapFree-x86_64.AppImage
  ```
  Di beberapa distro perlu paket `fuse`: `sudo apt install -y fuse`
- **Pip:** setelah COLMAP terpasang, `pip install mapfree` (atau `pip install -e .` dari sumber).

## Verifikasi instalasi

1. **GUI:** jalankan `mapfree gui` (atau buka MapFree.exe / AppImage). Jendela utama MapFree harus terbuka.
2. **Dependency checker:** saat startup, MapFree menampilkan dialog jika COLMAP atau dependency lain tidak ditemukan; ikuti petunjuk di dialog.
3. **CLI:** jalankan `mapfree run --help`. Pastikan perintah `run` dan opsi `--output` / `--open-results` tampil.

Setelah langkah di atas berhasil, Anda siap membuat project (lihat [02 — Membuat project](02_membuat_project.md)).
