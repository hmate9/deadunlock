# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

# Get the directory where this spec file is located
# Use os.getcwd() as fallback if __file__ is not available
try:
    project_root = Path(__file__).resolve().parent
except NameError:
    project_root = Path(os.getcwd())

icon_file = project_root / 'img' / 'deadunlock_icon.ico'

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('version.txt', '.'),
        ('img/deadunlock_icon.png', 'img'),
        ('img/deadunlock_icon.ico', 'img'),
        (str(icon_file), 'img'),
    ],
    hiddenimports=[
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'pygame',
        'psutil',
        'pymem',
        'win32api',
        'win32con',
        'win32gui',
        'pywintypes',
        'requests',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'json',
        'threading',
        'dataclasses',
        'ctypes',
        'struct',
        'logging',
        'argparse',
        'subprocess',
        'sys',
        'os',
        'time',
        'math',
        'random',
        'enum',
        'typing',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='deadunlock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file),
)
