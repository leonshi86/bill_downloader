# -*- mode: python ; coding: utf-8 -*-
# bill_downloader.spec — PyInstaller 打包配置
# 用法: pyinstaller bill_downloader.spec

import sys, os
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "email_downloader",
        "config",
    ],
    hookspath=[],
    keys=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bill_downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="bill_downloader",
)
