#!/usr/bin/env python3
"""Merge two single-arch PyInstaller bundles into one universal2 bundle.

    python3 appbuild/merge_universal.py <arm64.app> <x86_64.app> <out.app>

Strategy (the standard two-venv PyInstaller recipe): build the app once per
architecture, then walk every Mach-O file (bootloader exe, .dylib, .so
extensions) and fuse the two slices with ``lipo -create``. Pure-Python files
are arch-neutral — the arm64 copy wins. If a Mach-O only exists on one side
(e.g. an arch-specific optional dep), it is carried over as-is and counted
as a single-arch leftover so the build log stays honest.

The merged binaries have BROKEN signatures (lipo rewrites the bytes) — the
caller must re-codesign the whole bundle afterwards (build_release.sh does).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Mach-O magics: 32/64-bit thin (either byte order) and fat/universal.
_MACHO_MAGICS = {
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",  # MH_MAGIC[_64] swapped/native
    b"\xfe\xed\xfa\xbf",
    b"\xbf\xfa\xed\xfe",  # 32-bit variants
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",  # FAT_MAGIC
    b"\xca\xfe\xfa\xed",
    b"\xed\xfa\xfe\xca",  # FAT_MAGIC_64
}


def is_macho(path: Path) -> bool:
    """Mach-O probe by magic bytes (lipo -info is NOT reliable for thin files:
    it prints 'Non-fat file:' without the word 'Mach-O' and exits non-zero)."""
    try:
        with path.open("rb") as fh:
            return fh.read(4) in _MACHO_MAGICS
    except OSError:
        return False


def lipo_archs(path: Path) -> set[str]:
    r = subprocess.run(["lipo", "-archs", str(path)], capture_output=True, text=True)
    return set(r.stdout.split()) if r.returncode == 0 else set()


def merge_file(arm: Path, x86: Path, out: Path) -> None:
    tmp = out.with_suffix(out.suffix + ".lipo-tmp")
    subprocess.run(["lipo", "-create", "-output", str(tmp), str(arm), str(x86)], check=True)
    shutil.move(tmp, out)


def main(arm_app: Path, x86_app: Path, out_app: Path) -> int:
    for app in (arm_app, x86_app):
        if not (app / "Contents").is_dir():
            print(f"error: not a bundle: {app}", file=sys.stderr)
            return 2
    if out_app.exists():
        shutil.rmtree(out_app)
    shutil.copytree(arm_app, out_app, symlinks=True)

    stats = {"merged": 0, "single_arch": 0, "skipped_identical": 0}
    for f in sorted(out_app.rglob("*")):
        if not f.is_file() or f.is_symlink():
            continue
        rel = f.relative_to(out_app)
        mate = x86_app / rel
        if not mate.is_file():
            continue
        arm_bytes, x86_bytes = f.read_bytes(), mate.read_bytes()
        if arm_bytes == x86_bytes:
            stats["skipped_identical"] += 1
            continue
        if is_macho(f) and is_macho(mate):
            a_archs, m_archs = lipo_archs(f), lipo_archs(mate)
            if a_archs & m_archs:
                # overlapping slices (or one side already fat) — keep arm64
                stats["single_arch"] += 1
                print(f"  ! arch overlap {a_archs | m_archs}, kept arm: {rel}")
                continue
            merge_file(f, mate, f)
            stats["merged"] += 1
        # non-Mach-O differing files (e.g. recorded paths): arm copy already in place

    exe = out_app / "Contents" / "MacOS" / next(p.name for p in (out_app / "Contents" / "MacOS").iterdir())
    final = lipo_archs(exe)
    print(f"merge done: {stats} | universal exe archs: {sorted(final)}")
    if "arm64" not in final or "x86_64" not in final:
        print("error: bootloader is not universal2", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(*(Path(a).resolve() for a in sys.argv[1:])))
