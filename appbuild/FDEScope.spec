# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FDE Scope.app (macOS double-click workbench).

Build (from repo root, needs .venv-build with the [web] extra installed):

    .venv-build/bin/pyinstaller appbuild/FDEScope.spec --clean --noconfirm

Output: appbuild/dist/FDE Scope.app  (see appbuild/build_dmg.sh for the DMG step).

Design notes:
  * onedir (not onefile): faster cold start, sane crash logs, DMG-friendly.
  * ``fde_scope/templates`` must ship inside the bundle — report.py and
    operationalization.py resolve it via ``__file__`` (FileSystemLoader).
  * The launcher passes the app *object* to uvicorn (no import string, no
    reload/workers) — the frozen-safe single-process pattern.
"""

import pathlib

# The spec may run from any CWD; anchor everything to the repo root
# (one level up from this file: appbuild/ -> repo).
REPO_ROOT = pathlib.Path(SPECPATH).resolve().parent  # noqa: F821

# Templates are resolved from the repo source (the package is installed
# editable from here; ``__file__``-relative lookup happens at runtime too).
tmpl = REPO_ROOT / "fde_scope" / "templates"
assert tmpl.is_dir(), f"templates dir not found: {tmpl}"

# Provenance file written by build_release.sh; absent for plain dev builds.
build_info = REPO_ROOT / "appbuild" / "build_info.json"
datas = [(str(tmpl), "fde_scope/templates")]
if build_info.is_file():
    datas.append((str(build_info), "."))

a = Analysis(
    [str(REPO_ROOT / "appbuild" / "launcher.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # uvicorn loads these protocol/lifespan implementations by name at runtime
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # optional [web] deps pulled in dynamically
        "multipart",
        "python_multipart",
        "anyio._backends._asyncio",
        "jinja2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL", "numpy", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FDE Scope",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed: no Terminal popping up on double-click
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(REPO_ROOT / "appbuild" / "FDEScope.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FDE Scope",
)

app = BUNDLE(
    coll,
    name="FDE Scope.app",
    icon=str(REPO_ROOT / "appbuild" / "FDEScope.icns"),
    bundle_identifier="global.ai_guru.fde.scope",
    info_plist={
        "CFBundleDisplayName": "FDE Scope",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "NSHumanReadableCopyright": "MIT License — ai-guru-global",
    },
)
