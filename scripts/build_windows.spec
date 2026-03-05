# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for MapFree GUI on Windows.
# Run: pyinstaller scripts/build_windows.spec --clean --noconfirm
# Output: dist/MapFree/MapFree.exe (folder distribution; onefile=False for PySide6 stability)

import sys
from pathlib import Path

# Repo root (spec is in scripts/, so parent of SPECPATH)
block_cipher = None
root = Path(SPECPATH).resolve().parent

# Entry point: GUI only (mapfree gui)
script = str(root / "mapfree" / "app.py")

# Data files: QSS, icons, map assets
resources_dir = root / "mapfree" / "gui" / "resources"
datas = [(str(resources_dir), "mapfree/gui/resources")]

# Icon (placeholder or real mapfree.ico)
icon_path = root / "mapfree" / "gui" / "resources" / "icons" / "mapfree.ico"
icon = str(icon_path) if icon_path.is_file() else None

# Hidden imports so PyInstaller includes them (dynamic imports / optional deps)
hidden_imports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "numpy",
    "yaml",
    "psutil",
]
try:
    import pyqtgraph
    hidden_imports.append("pyqtgraph")
    hidden_imports.append("pyqtgraph.opengl")
except ImportError:
    pass
try:
    import cv2
    hidden_imports.append("cv2")
except ImportError:
    pass

# Exclude tests, docs, dev artifacts
excludes = [
    "pytest",
    "pytest_mock",
    "pytest_cov",
    "flake8",
    "setuptools",
    "distutils",
]

a = Analysis(
    [script],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onefile=False: folder distribution (more stable for PySide6)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MapFree",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MapFree",
)

# Build: pyinstaller scripts/build_windows.spec --clean --noconfirm
# Result: dist/MapFree/MapFree.exe + DLLs and dependencies
