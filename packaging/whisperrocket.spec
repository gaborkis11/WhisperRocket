# -*- mode: python ; coding: utf-8 -*-
"""
WhisperRocket PyInstaller Spec
AppImage build - excludes CUDA libraries (runtime download)
"""

import sys
from pathlib import Path

# Project root (parent of packaging directory)
# SPECPATH is provided by PyInstaller and points to the spec file's directory
project_root = Path(SPECPATH).resolve().parent

# Data files to include
datas = [
    (str(project_root / 'assets'), 'assets'),
    (str(project_root / 'platform_support'), 'platform_support'),
    (str(project_root / 'appimage_uninstall.py'), '.'),
]

# Hidden imports
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'sounddevice',
    'soundfile',
    'pyperclip',
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._xorg',
    'PIL',
    'numpy',
    'faster_whisper',
    'ctranslate2',
    'huggingface_hub',
    'tokenizers',
    'evdev',
    'requests',
    # AI cleanup modules. whisper_gui imports these lazily inside a function so
    # that plain dictation keeps working if they are missing, which means static
    # analysis is not guaranteed to find them - list them explicitly.
    'ai_enhancer',
    'ai_guard',
    'claude_cli',
    'dictionary_manager',
    'qt_helpers',
    # Phone dictation, lazily imported for the same reason and needing the same
    # treatment: without these the tray app still runs, so a missing module would
    # not announce itself - the Phone tab would simply refuse to start the
    # endpoint, in a build nobody had reason to suspect.
    'phone_endpoint',
    'tailscale_support',
    'secrets_manager',
]

# Exclude CUDA libraries (downloaded at runtime)
excludes = [
    'nvidia.cudnn',
    'nvidia.cublas',
    'nvidia.cuda_runtime',
    'nvidia.cuda_nvrtc',
]

# Binary exclusions (reduce size - only CUDA, Qt6 is REQUIRED!)
binaries_exclude = [
    'nvidia',  # All NVIDIA libraries (downloaded at runtime)
]

a = Analysis(
    [str(project_root / 'whisper_gui.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# Filter out excluded binaries
a.binaries = [
    (name, path, typecode)
    for name, path, typecode in a.binaries
    if not any(excl in name for excl in binaries_exclude)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='whisperrocket',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='whisperrocket',
)
