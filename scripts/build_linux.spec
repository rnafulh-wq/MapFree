# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for MapFree GUI on Linux (AppImage).
# Run: pyinstaller scripts/build_linux.spec --clean
# Then: scripts/build_linux.sh packages dist/MapFree into MapFree-x86_64.AppImage

from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent

script = str(root / "mapfree" / "app.py")
resources_dir = root / "mapfree" / "gui" / "resources"
datas = [(str(resources_dir), "mapfree/gui/resources")]

# PNG icon for .desktop (optional in spec; used in AppDir by build_linux.sh)
icon_png = root / "mapfree" / "gui" / "resources" / "icons" / "mapfree.png"
if icon_png.is_file():
    datas.append((str(icon_png), "mapfree/gui/resources/icons"))

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
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MapFree",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
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
