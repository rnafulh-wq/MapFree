# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for MapFree desktop app.
# Install: pip install pyinstaller
# Build:   pyinstaller mapfree.spec
# (Equivalent to: pyinstaller --onefile --windowed -n MapFree mapfree/app.py
#  but with hiddenimports and datas so no missing imports.)

import sys
from pathlib import Path

block_cipher = None

# Project root (parent of mapfree/)
project_root = Path(SPECPATH).resolve()

# Ensure mapfree package is found when analyzing mapfree/app.py
pathex = [str(project_root)]

# Hidden imports PyInstaller may not detect
hiddenimports = [
    'mapfree',
    'mapfree.gui',
    'mapfree.gui.main_window',
    'mapfree.gui.panels',
    'mapfree.gui.panels.project_panel',
    'mapfree.gui.panels.console_panel',
    'mapfree.gui.panels.progress_panel',
    'mapfree.gui.panels.viewer_panel',
    'mapfree.gui.qt_controller',
    'mapfree.gui.workers',
    'mapfree.gui.dialogs',
    'mapfree.application',
    'mapfree.application.controller',
    'mapfree.core',
    'mapfree.core.context',
    'mapfree.core.event_bus',
    'mapfree.core.pipeline',
    'mapfree.core.engine',
    'mapfree.core.state',
    'mapfree.core.config',
    'mapfree.core.logger',
    'mapfree.core.events',
    'mapfree.core.validation',
    'mapfree.core.wrapper',
    'mapfree.core.chunking',
    'mapfree.core.hardware',
    'mapfree.core.profiles',
    'mapfree.core.final_results',
    'mapfree.engines',
    'mapfree.engines.colmap_engine',
    'mapfree.engines.openmvs_engine',
    'mapfree.config',
    'mapfree.utils',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
]

# Bundle QSS and default config so they are available at runtime
datas = [
    (str(project_root / 'mapfree' / 'gui' / 'resources'), 'mapfree/gui/resources'),
    (str(project_root / 'mapfree' / 'config'), 'mapfree/config'),
]

a = Analysis(
    ['mapfree/app.py'],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MapFree',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # windowed (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
