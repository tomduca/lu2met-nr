# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the LU2MET NR Filter desktop app (macOS and Windows).
# Build with build_macos.sh or build_windows.ps1; they set APP_VERSION.
import os
import sys

from PyInstaller.utils.hooks import collect_all, copy_metadata

APP_NAME = 'LU2MET_NR'
APP_VERSION = os.environ.get('APP_VERSION', '0.0.0')
IS_MACOS = sys.platform == 'darwin'

datas, binaries, hiddenimports = [], [], []
for package in ('novasdr_nr', 'sounddevice'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
datas += copy_metadata('numpy') + copy_metadata('scipy')

a = Analysis(
    ['novasdr_gui_qt.py'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ['_sounddevice', 'scipy.signal', 'pydub'],
    excludes=['pytest', 'tkinter', 'flask', 'scipy.tests', 'numpy.tests', 'PyQt5.tests'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,
    icon='app_icon.icns' if IS_MACOS else 'app_icon.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name=APP_NAME)

if IS_MACOS:
    app = BUNDLE(
        coll,
        name=f'{APP_NAME}.app',
        icon='app_icon.icns',
        bundle_identifier='com.lu2met.nr',
        version=APP_VERSION,
        info_plist={
            'CFBundleDisplayName': 'LU2MET NR Filter',
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleVersion': APP_VERSION,
            'NSHighResolutionCapable': True,
            'NSMicrophoneUsageDescription':
                'LU2MET NR Filter needs access to audio input devices to process radio signals.',
        },
    )
