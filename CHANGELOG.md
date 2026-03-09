# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.1.0] - 2026-03-05

MapFree Engine v1.1.0 — Smart Installer & Hardware Detection.

### Added

- **Smart installer & first-run wizard**
  - Hardware detection module (CPU, RAM, GPU, CUDA) for Windows/Linux/macOS
  - Dependency resolver: COLMAP (CUDA/no-CUDA), optional OpenMVS, PDAL, GDAL
  - Dependency downloader with progress, retry, and install (zip/exe/choco/apt)
  - First-run setup wizard (4 pages): Welcome, Hardware, Components, Install
  - `~/.mapfree/setup_complete.json` to skip wizard after setup
- **PATH management**
  - `PathManager`: deps registry (`~/.mapfree/deps_registry.json`), `inject_to_env()` at startup
  - `app.py` and CLI call `PathManager.inject_to_env()` before other imports
  - `dependency_check` prefers MapFree-registered binaries over system PATH
  - Wizard registers installed COLMAP/OpenMVS binaries after install
- **Windows installer**
  - Inno Setup script (`scripts/installer/mapfree_setup.iss`) with hardware/components pages
  - Release workflow: build Windows installer + portable zip, upload to GitHub Release
- **Linux installer**
  - `install_linux.sh`: distro detection, GPU, RAM, install COLMAP, copy AppImage
  - `create_desktop_entry.sh`: mapfree.desktop and icon, update-desktop-database

### Changed

- Release assets: MapFree-Setup-1.1.0.exe (recommended), MapFree-windows-portable.zip, AppImage

## [1.0.0] - 2026-03-05

### Added

- 3D point cloud viewer menggunakan PyQtGraph
- 3D mesh viewer dengan shading dan wireframe toggle
- Live preview point cloud saat sparse reconstruction
- Sistem lisensi offline dengan HMAC validation
- Trial mode 30 hari
- License activation dialog
- Startup dependency checker dengan install hints
- Installer PowerShell untuk Windows
- Project history panel (10 project terakhir)
- Settings dialog (paths, hardware profile, pipeline options)
- Structured file logging dengan rotation
- Crash report otomatis ke output folder
- User guide (5 bab: instalasi, project, pipeline, hasil, troubleshooting)
- PyInstaller build Windows + Linux AppImage
- GitHub Actions release workflow (tag v*.*.* → build + GitHub Release)
- Performance & memory tests (pipeline 50 images, EventBus leak, concurrent pipelines)
- Security tests (path traversal, YAML safe_load)

### Fixed

- .mapfree_state.json tidak lagi di-commit ke Git
- URL placeholder di README sudah difix
- OpenGL viewer tidak crash jika GPU tidak mendukung
- Semua subprocess calls tidak menggunakan shell=True

### Security

- Validasi path traversal untuk semua user input (project_path, image_path)
- yaml.safe_load dipakai di semua config parsing
- Shell injection vulnerability di engine calls diperbaiki (list args only)

## [0.1.0] - Initial Desktop Release

### Added

- PySide6 native desktop GUI (main window, project/console/progress/viewer panels, dark theme).
- Event-driven pipeline with EventBus; Qt controller and worker for non-blocking UI.
- Modular engine layer (COLMAP, OpenMVS); CLI and GUI entry points.
- Structured logging, production-style layout (core, application, gui, utils).

[Unreleased]: https://github.com/rnafulh-wq/MapFree/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/rnafulh-wq/MapFree/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/rnafulh-wq/MapFree/releases/tag/v1.0.0
[0.1.0]: https://github.com/rnafulh-wq/MapFree/releases/tag/v0.1.0
