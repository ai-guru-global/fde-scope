#!/usr/bin/env bash
# Production release build for FDE Scope.app (macOS).
#
#   ./appbuild/build_release.sh [--arch arm64|x86_64|universal] [--no-dmg]
#
# What this adds over build_dmg.sh (dev convenience script):
#   * versioned build_info.json baked into the bundle (provenance logging)
#   * universal2 support: one venv per arch + lipo merge (merge_universal.py)
#   * hardened-runtime codesign with appbuild/entitlements.plist; if a
#     Developer ID certificate exists in the keychain, it signs with it and
#     notarizes the DMG (xcrun notarytool, needs NOTARIZE_* env or a stored
#     notary profile). Without a cert it falls back to ad-hoc signing.
#   * prettier DMG (Finder window layout, best-effort) + sha256 manifest
#
# Outputs land in appbuild/dist/:
#   FDE Scope.app  FDE-Scope-<version>-<arch>.dmg  manifest.json  SHA256SUMS
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT=$PWD

ARCH=universal
MAKE_DMG=1
while [ $# -gt 0 ]; do
  case "$1" in
    --arch) ARCH=$2; shift 2 ;;
    --arch=*) ARCH=${1#*=}; shift ;;
    --no-dmg) MAKE_DMG=0; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
case "$ARCH" in arm64|x86_64|universal) ;; *) echo "bad --arch: $ARCH" >&2; exit 2 ;; esac

VERSION=$(python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
GIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo unknown)
GIT_DIRTY=$(git status --porcelain 2>/dev/null | grep -c . || true)
BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DIST=appbuild/dist
SPECF="appbuild/FDEScope.spec"
ENTITLEMENTS=appbuild/entitlements.plist
IDENTITIES=$(security find-identity -v -p codesigning 2>/dev/null || true)
if grep -q "Developer ID Application" <<<"$IDENTITIES"; then
  SIGN_IDENTITY=$(grep -m1 -o '"Developer ID Application: [^"]*"' <<<"$IDENTITIES" | tr -d '"')
else
  SIGN_IDENTITY="-"
fi

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*" >&2; }

# ---------- provenance -------------------------------------------------------
write_build_info() { # $1 = arch label
  python3 - "$VERSION" "$GIT_SHA" "$BUILD_TIME" "$1" "$GIT_DIRTY" <<'PY'
import json, sys
json.dump({
    "version": sys.argv[1], "git_sha": sys.argv[2], "build_time": sys.argv[3],
    "arch": sys.argv[4], "git_dirty": sys.argv[5] != "0",
}, open("appbuild/build_info.json", "w"), indent=2)
PY
}

# ---------- per-arch venv + pyinstaller -------------------------------------
# NOTE: these helpers communicate via globals, never via stdout — bundles paths
# contain spaces and $(func) capture would mangle them.
build_one() { # $1 = arch ; sets BUILT_APP
  local arch=$1 venv py out
  case $arch in
    arm64)  venv=.venv-build-arm64  py=cpython-3.12-macos-aarch64-none ;;
    x86_64) venv=.venv-build-x86_64 py=cpython-3.12-macos-x86_64-none ;;
  esac
  write_build_info "$arch"
  if [ ! -x "$venv/bin/pyinstaller" ]; then
    log "creating $arch venv ($venv)"
    uv venv --python "$py" "$venv"
  fi
  log "installing build deps ($arch)"
  uv pip install --python "$venv/bin/python" -e ".[web]" pyinstaller >/dev/null
  # Clear caches and any stale bundle (a nested leftover inside the .app
  # poisons codesign with "unsealed contents present in the bundle root").
  rm -rf "appbuild/build/FDE Scope-$arch" "$DIST/FDE Scope.app" "appbuild/dist/FDE Scope"
  log "pyinstaller build ($arch)"
  "$venv/bin/pyinstaller" "$SPECF" \
    --distpath "$DIST" \
    --workpath "appbuild/build/FDE Scope-$arch" \
    --clean --noconfirm >/dev/null
  out="$DIST/FDE Scope.app"
  [ -d "$out" ] || { echo "error: build produced no bundle at $out" >&2; return 1; }
  lipo -archs "$out/Contents/MacOS/FDE Scope" | grep -q "$arch" \
    || { echo "error: built bundle is not $arch" >&2; return 1; }
  BUILT_APP=$out
}

# ---------- signing -----------------------------------------------------------
# NOTE: the repo lives under iCloud Drive on many dev machines; FileProvider
# re-attaches com.apple.FinderInfo / fileprovider xattrs to freshly-written
# directories faster than any purge can keep up, and codesign then aborts with
# "resource fork, Finder information, or similar detritus not allowed".
# All signing + DMG assembly therefore happens under /tmp (a non-synced path),
# and only finished, signed artifacts are copied back into dist/.
sign_bundle() { # $1 = path to .app or .dmg ; deep-sign with hardened runtime
  local target=$1
  log "codesign $target (identity: $SIGN_IDENTITY)"
  [ -d "$target" ] && xattr -cr "$target" 2>/dev/null || true
  # Inside-out: every Mach-O first, bundle last with entitlements.
  find "$target" -type f \( -name '*.so' -o -name '*.dylib' \) -print0 2>/dev/null \
    | xargs -0 -r codesign --force --sign "$SIGN_IDENTITY" --options runtime >/dev/null
  codesign --force --deep --sign "$SIGN_IDENTITY" --options runtime \
    --entitlements "$ENTITLEMENTS" --timestamp "$target"
  codesign --verify --deep --strict --verbose=2 "$target" >/dev/null
}

maybe_notarize() { # $1 = artifact to notarize + staple (DMG only)
  local target=$1 profile=${NOTARY_PROFILE:-fde-scope}
  if [ "$SIGN_IDENTITY" = "-" ]; then
    log "ad-hoc build: skipping notarization (needs a Developer ID certificate)"
    return 0
  fi
  if [ -n "${NOTARIZE_API_KEY_ID:-}" ] && [ -n "${NOTARIZE_API_KEY_PATH:-}" ] && [ -n "${NOTARIZE_API_KEY_ISSUER:-}" ]; then
    log "notarizing $target (notarytool, API key)"
    xcrun notarytool submit "$target" \
      --key-id "$NOTARIZE_API_KEY_ID" \
      --issuer "$NOTARIZE_API_KEY_ISSUER" \
      --key "$NOTARIZE_API_KEY_PATH" \
      --wait
  else
    log "notarizing $target (notarytool, keychain profile '$profile')"
    xcrun notarytool submit "$target" --keychain-profile "$profile" --wait
  fi
  xcrun stapler staple "$target"
}

# ---------- DMG ---------------------------------------------------------------
make_dmg() { # $1 = stage dir containing app + Applications symlink ; $2 = output dmg
  local stage=$1 dmg=$2 vol="FDE Scope $VERSION" rw
  rm -f "$dmg"
  # Best-effort polished DMG: build on a writable image, arrange the Finder
  # window, then convert to compressed. Any hiccup → plain hdiutil fallback.
  rw="${dmg%.dmg}-rw.dmg"
  rm -f "$rw"
  if hdiutil create -volname "$vol" -srcfolder "$stage" -format UDRW -size 200m "$rw" >/dev/null 2>&1 \
    && hdiutil attach -readwrite -noverify -noautoopen "$rw" >/dev/null 2>&1; then
    local mnt="/Volumes/$vol"
    # shellcheck disable=SC2050
    osascript <<APPLESCRIPT || true
tell application "Finder"
  tell disk "$vol"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set the statusbar visible of container window to false
    set bounds of container window to {180, 100, 760, 420}
    set theViewOptions to icon view options of container window
    set arrangement of theViewOptions to not arranged
    set icon size of theViewOptions to 96
    set position of item "FDE Scope.app" of container window to {140, 150}
    set position of item "Applications" of container window to {440, 150}
    update without registering applications
    delay 2
    close
  end tell
end tell
APPLESCRIPT
    sync; hdiutil detach "$mnt" >/dev/null 2>&1 || hdiutil detach -force "$mnt" >/dev/null
    if hdiutil convert "$rw" -format UDZO -o "$dmg" >/dev/null 2>&1; then
      rm -f "$rw"
      return 0
    fi
    rm -f "$rw"
  fi
  log "falling back to plain DMG (no Finder customization)"
  hdiutil create -volname "$vol" -srcfolder "$stage" -ov -format UDZO "$dmg" >/dev/null
}

# ---------- main flow ---------------------------------------------------------
# Sign/DMG workspace outside iCloud-synced paths (see signing note above).
WORK=$(mktemp -d /tmp/fde-scope-release.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
case $ARCH in
  arm64|x86_64)
    build_one "$ARCH"
    APP="$WORK/FDE Scope.app"
    mv "$DIST/FDE Scope.app" "$APP"
    FINAL_ARCH=$ARCH
    ;;
  universal)
    build_one arm64
    mv "$DIST/FDE Scope.app" "$WORK/FDE Scope-arm64.app"
    build_one x86_64
    mv "$DIST/FDE Scope.app" "$WORK/FDE Scope-x86_64.app"
    write_build_info universal2
    log "merging universal2 bundle"
    python3 appbuild/merge_universal.py \
      "$WORK/FDE Scope-arm64.app" \
      "$WORK/FDE Scope-x86_64.app" \
      "$WORK/FDE Scope.app"
    APP="$WORK/FDE Scope.app"
    rm -rf "$WORK/FDE Scope-arm64.app" "$WORK/FDE Scope-x86_64.app"
    FINAL_ARCH=universal2
    ;;
esac

sign_bundle "$APP"

if [ "$MAKE_DMG" = 1 ]; then
  DMG="$WORK/FDE-Scope-$VERSION-$FINAL_ARCH.dmg"
  STAGE="$WORK/dmg-stage"
  log "packaging DMG → $DMG"
  mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  make_dmg "$STAGE" "$DMG"
  rm -rf "$STAGE"
  sign_bundle "$DMG"
  maybe_notarize "$DMG"
  cp -f "$DMG" "$DIST/"
  DMG="$DIST/$(basename "$DMG")"
else
  DMG=""
fi

# Published copy of the signed app back into dist/ — plus a .zip for
# distribution. NOTE: an unpacked .app cannot live reliably under iCloud
# Drive: FileProvider re-attaches com.apple.FinderInfo to synced directories,
# which makes `codesign --verify` on the *loose* copy abort with "detritus
# not allowed". The signature bytes are unaffected (verify inside this script
# ran on /tmp before sealing); distribute the zip, not the folder.
rm -rf "$DIST/FDE Scope.app"
cp -R "$APP" "$DIST/"
ditto -c -k --keepParent "$APP" "$WORK/FDE-Scope-$VERSION-$FINAL_ARCH.zip"
cp -f "$WORK/FDE-Scope-$VERSION-$FINAL_ARCH.zip" "$DIST/"
ZIP="$DIST/FDE-Scope-$VERSION-$FINAL_ARCH.zip"

# ---------- manifest ----------------------------------------------------------
log "release manifest"
rm -f "$DIST/SHA256SUMS" "$DIST/manifest.json"
if [ -n "$DMG" ]; then
  ( cd "$DIST" && shasum -a 256 "$(basename "$DMG")" "$(basename "$ZIP")" ) > "$DIST/SHA256SUMS"
else
  : > "$DIST/SHA256SUMS"
fi
python3 - "$VERSION" "$GIT_SHA" "$BUILD_TIME" "$FINAL_ARCH" "$SIGN_IDENTITY" "$DMG" <<'PY'
import json, subprocess, sys, pathlib
version, git_sha, build_time, arch, identity, dmg = sys.argv[1:7]
digest = ""
targets = [dmg] if dmg else []
if digest == "" and targets:
    out = subprocess.run(["shasum", "-a", "256", *targets], capture_output=True, text=True).stdout
    digest = out.splitlines()[0].split()[0] if out else ""
manifest = {
    "product": "FDE Scope", "version": version, "git_sha": git_sha,
    "build_time": build_time, "arch": arch,
    "signing": "developer-id" if identity != "-" else "ad-hoc",
    "notarized": identity != "-",
    "artifacts": {("dmg" if dmg else "app"): dmg or "FDE Scope.app"},
    "sha256_dmg": digest,
}
pathlib.Path("appbuild/dist/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
PY

echo
echo "done:"
echo "  app: $DIST/FDE Scope.app   ($(lipo -archs "$DIST/FDE Scope.app/Contents/MacOS/FDE Scope"))"
[ -n "$DMG" ] && echo "  dmg: $DMG"
[ -n "${ZIP:-}" ] && echo "  zip: $ZIP"
echo "  signing: $SIGN_IDENTITY"
exit 0
