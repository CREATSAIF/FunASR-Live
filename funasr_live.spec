# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for FunASR Live (Hotkey mode)
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all necessary data files
datas = [
    ('config.yaml', '.'),
    ('model.py', '.'),
]

# Collect hidden imports
hiddenimports = [
    'funasr',
    'funasr.auto',
    'torch',
    'torchaudio',
    'sounddevice',
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._darwin',
    'pynput.keyboard._win32',
    'pynput.keyboard._xorg',
    'pyperclip',
    'yaml',
    'numpy',
    'scipy',
    'sklearn',
    'modelscope',
]

# Platform-specific settings
if sys.platform == 'darwin':
    hiddenimports.extend([
        'pynput.keyboard._darwin',
        'AppKit',
        'Foundation',
    ])
elif sys.platform == 'win32':
    hiddenimports.extend([
        'pynput.keyboard._win32',
        'win32api',
        'win32con',
    ])
else:
    hiddenimports.extend([
        'pynput.keyboard._xorg',
    ])

a = Analysis(
    ['funasr_live.py'],
    pathex=[],
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
    a.zipfiles,
    a.datas,
    [],
    name='FunASR-Live',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
