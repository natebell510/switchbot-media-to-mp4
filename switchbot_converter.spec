# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — run: pyinstaller switchbot_converter.spec

import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Bundle tkinterdnd2 shared library
dnd_datas = collect_data_files("tkinterdnd2")
dnd_bins  = collect_dynamic_libs("tkinterdnd2")

a = Analysis(
    ['switchbot_converter.py'],
    pathex=[],
    binaries=dnd_bins,
    datas=dnd_datas,
    hiddenimports=['tkinterdnd2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SwitchBot_Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # no console window — GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
