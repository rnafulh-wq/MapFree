# Release v1.1.0 — Checklist

## 1. CI hijau
- [x] `flake8 mapfree/ tests/ --config=.flake8` — pass
- [x] `pytest tests/ --ignore=tests/gui --ignore=tests/integration --cov=mapfree --cov-fail-under=58` — 568 passed, 60.92% coverage
- [ ] GitHub Actions: push/PR ke `develop` (atau `main`) — pastikan workflow Lint + Test hijau

## 2. Tag v1.1.0
**Status:** Tag `v1.1.0` sudah ada (lokal & remote). Release workflow sudah pernah jalan untuk tag ini.
- [x] Tag ada di remote → build Windows/Linux/installer sudah (atau akan) jalan di Actions
- Jika ingin rilis dari commit **terkini** (develop): hapus tag lalu buat ulang (hati-hati: mengubah history release):
  ```powershell
  git tag -d v1.1.0
  git push origin :refs/tags/v1.1.0
  git tag -a v1.1.0 -m "Release v1.1.0 - Smart Installer & Hardware Detection"
  git push origin v1.1.0
  ```

## 3. Test installer di Windows (setelah artifact tersedia)
- [ ] Unduh **MapFree-Setup-1.1.0.exe** dari GitHub Actions artifacts (job `build-windows-installer`) atau dari Draft Release setelah workflow selesai
- [ ] Jalankan installer di mesin Windows (admin jika diminta)
- [ ] Pastikan: install ke folder default, shortcut Start Menu/Desktop (jika dipilih)
- [ ] Launch MapFree dari shortcut → jendela utama terbuka
- [ ] Cek: Help → Periksa Dependency (atau first-run wizard jika belum setup)
- [ ] (Opsional) Buat project, Add Photos, pilih output, Run → pastikan tidak crash
- [ ] Uninstall via Add/Remove Programs — bersih

## 4. Release publish
- [ ] Setelah workflow "Create GitHub Release" selesai, buka **Releases** di repo
- [ ] Jika release dibuat sebagai draft: edit release → uncheck "Set as a pre-release" jika ini rilis resmi → Publish
- [ ] Verifikasi asset: MapFree-Setup-1.1.0.exe, MapFree-windows-portable.zip, MapFree-x86_64.AppImage, checksums.txt
- [ ] Body release diisi dari CHANGELOG (workflow sudah extract dari CHANGELOG.md)

## 5. Post-release
- [ ] Merge `develop` → `main` (jika rilis dari develop)
- [ ] Update doc/roadmap jika ada "Release v1.1.0 tersedia di GitHub" checklist

---
*Setelah selesai, release v1.1.0 siap diumumkan.*
