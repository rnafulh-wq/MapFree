# MapFree Documentation — Improvements Summary

Dokumen ini merangkum semua perubahan yang dilakukan pada dokumentasi MapFree
dan alasan di balik setiap perubahan.

---

## Ringkasan Perubahan

### LICENSE — Ganti MIT → AGPL v3 (KRITIS)

**Masalah:** LICENSE lama menggunakan MIT.

**Mengapa salah:** MapFree menggunakan OpenMVS yang berlisensi
GNU Affero General Public License v3.0 (AGPL v3). Mendistribusikan
software yang menggunakan library AGPL v3 dengan lisensi MIT adalah
pelanggaran lisensi secara hukum karena AGPL v3 bersifat copyleft —
turunannya harus ikut AGPL v3.

**Fix:** Ganti ke AGPL v3 dengan tabel dependency licenses untuk transparansi.

**Implikasi AGPL v3 untuk pengguna MapFree:**
- Bebas dipakai, dimodifikasi, dan didistribusikan ulang
- Modifikasi harus dibagikan dengan source code (termasuk jika dijalankan
  sebagai layanan cloud/server)
- Tidak bisa dijadikan proprietary software tanpa izin pemegang hak

---

### README.md — Ditulis Ulang

**Masalah di README lama:**

| Masalah | Detail |
|---------|--------|
| Instruksi instalasi salah | Pakai `python -m venv` — tidak kompatibel dengan GDAL/PDAL |
| Python version salah | Ditulis 3.8+, MapFree pakai 3.11 di conda |
| CLI command salah | `mapfree --input ... --output ...` tidak sesuai argumen yang ada |
| Project structure salah | Masih tulis `pipeline/`, `colmap/`, `openmvs/` folder lama |
| License badge salah | MIT badge, padahal harus AGPL v3 |
| URL placeholder | `your-org/MapFree` belum diganti |
| Roadmap tidak sesuai | Tidak mencerminkan roadmap v2 yang sudah dibuat |
| Tidak ada System Requirements | Tidak ada info RAM, GPU, OS |
| Tidak ada Pipeline Overview | User tidak tahu alur kerja MapFree |

**Perubahan utama di README baru:**
- ✅ Logo MapFree di bagian atas
- ✅ Badge AGPL v3 yang benar
- ✅ Instalasi via conda (satu-satunya cara yang benar di Windows)
- ✅ Python 3.11
- ✅ CLI command yang benar: `python -m mapfree`
- ✅ Project structure sesuai kondisi repo sebenarnya
- ✅ Pipeline overview dengan diagram alur
- ✅ System requirements (RAM, GPU, OS, storage)
- ✅ Tabel dependency licenses
- ✅ Roadmap v1.1.0 → v1.7 sesuai MapFree_Roadmap_v2.md
- ✅ Troubleshooting untuk masalah yang sudah ditemukan di real-world testing

---

### CONTRIBUTING.md — Diperbarui

**Masalah di CONTRIBUTING lama:**

| Masalah | Detail |
|---------|--------|
| Setup pakai venv | Tidak bisa untuk GDAL/PDAL di Windows |
| Python 3.8 | Harus 3.11 |
| License reference ke MIT | Harus AGPL v3 |
| Tidak ada real-world testing guide | Penting untuk PR yang touch pipeline |
| Bug report template tidak lengkap | Tidak minta mapfree.log, GPU info |

**Perubahan utama di CONTRIBUTING baru:**
- ✅ Setup menggunakan conda (bukan venv)
- ✅ Python 3.11
- ✅ Langkah verify: gdalinfo, pdal, colmap, python -m mapfree
- ✅ Seksi Real-world Testing: wajib test dengan foto drone untuk PR pipeline
- ✅ Bug report template dengan field: mapfree.log, COLMAP version, GPU, foto count
- ✅ License reference ke AGPL v3
- ✅ Catatan penting: jangan pakai venv

---

### IMPROVEMENTS_SUMMARY.md — Dokumen Ini

File ini menjelaskan *mengapa* perubahan dilakukan, bukan sekadar *apa*
yang berubah. Berguna sebagai referensi saat ada pertanyaan tentang
keputusan dokumentasi.

---

## Checklist Sebelum Release v1.1.0

### LICENSE
- [x] Ganti MIT → AGPL v3
- [x] Tambahkan tabel dependency licenses
- [x] Update pyproject.toml: `license = {text = "AGPL-3.0-or-later"}`

### README.md
- [x] Badge AGPL v3
- [x] Logo MapFree
- [x] Instruksi conda
- [x] Python 3.11
- [x] Project structure akurat
- [x] Pipeline overview
- [x] System requirements
- [x] Roadmap v2
- [x] Dependency licenses tabel
- [ ] Screenshots GUI (tambahkan setelah v1.1.0 stabil)
- [ ] Docs folder (docs/installation.md, docs/user-guide.md)

### CONTRIBUTING.md
- [x] Setup via conda
- [x] Python 3.11
- [x] Real-world testing guide
- [x] Bug report template lengkap
- [x] License reference AGPL v3

---

## Catatan untuk Maintainer

**Dual Licensing (opsional di masa depan):**
Dengan AGPL v3, jika ada perusahaan yang ingin menggunakan MapFree
sebagai bagian dari produk komersial closed-source, mereka perlu
commercial license dari kamu. Ini model bisnis yang valid
(contoh: Qt, MongoDB, Metashape juga pakai model serupa).

**Kontributor Agreement:**
Semua kontributor setuju kode mereka masuk ke AGPL v3 via CONTRIBUTING.md.
Jika suatu saat ingin dual licensing, kamu perlu CLA (Contributor License
Agreement) untuk mendapat hak redistribusi di bawah lisensi lain.
