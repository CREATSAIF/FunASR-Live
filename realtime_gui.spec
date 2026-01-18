# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for FunASR Realtime GUI
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all necessary data files
datas = [
    ('config_realtime.yaml', '.'),
    ('model.py', '.'),
]

# Collect hidden imports
hiddenimports = [
    'funasr',
    'funasr.auto',
    'torch',
    'torchaudio',
    'sounddevice',
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.sip',
    'yaml',
    'numpy',
    'scipy',
    'sklearn',
    'modelscope',
    'fastapi',
    'uvicorn',
    'websockets',
]

# Platform-specific settings
if sys.platform == 'darwin':
    hiddenimports.extend([
        'AppKit',
        'Foundation',
    ])
elif sys.platform == 'win32':
    hiddenimports.extend([
        'win32api',
        'win32con',
    ])

a = Analysis(
    ['realtime_gui.py'],
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
    name='FunASR-GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI mode, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if available
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='FunASR-GUI.app',
        icon=None,
        bundle_identifier='com.creatsaif.funasr-gui',
        info_plist={
            'NSMicrophoneUsageDescription': 'FunASR needs microphone access for speech recognition.',
            'NSAppleEventsUsageDescription': 'FunASR needs accessibility access for keyboard simulation.',
        },
    )
