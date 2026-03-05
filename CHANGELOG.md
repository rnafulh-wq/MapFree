# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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

[Unreleased]: https://github.com/rnafulh-wq/MapFree/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/rnafulh-wq/MapFree/releases/tag/v1.0.0
[0.1.0]: https://github.com/rnafulh-wq/MapFree/releases/tag/v0.1.0
