# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — works on both macOS and Windows.
# Build with:  pyinstaller KarmedExport.spec
# PyInstaller resolves the data-file separator per OS, so this file is portable.
import sys

ICON = "assets/icon.icns" if sys.platform == "darwin" else "assets/icon.ico"

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[("karmed/static", "static")],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="KarmedExport",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,  # keep a window so errors are visible; closing it stops the server
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
