#!/usr/bin/env bash
# Build FDE Scope.app + FDE Scope.dmg for macOS (arm64/x86_64 = the host arch).
#
#   ./appbuild/build_dmg.sh
#
# Requires: uv (https://docs.astral.sh/uv) and repo deps for the [web] extra.
# Output:   appbuild/dist/FDE Scope.app          (double-click ready)
#           appbuild/dist/FDE-Scope-<version>.dmg (drag-to-Applications installer)
#
# The app is ad-hoc signed (no Apple Developer ID): first launch from a
# browser download needs right-click → Open. See docs/macos_app_packaging.md.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=.venv-build
PY=3.12
VERSION=$(python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])" 2>/dev/null \
  || grep -m1 '^version' pyproject.toml | cut -d'"' -f2)

if [ ! -x "$VENV/bin/pyinstaller" ]; then
  echo "==> creating build venv ($VENV, py$PY)"
  uv venv --python "$PY" "$VENV"
fi
echo "==> installing build deps into $VENV"
uv pip install --python "$VENV/bin/python" -e ".[web]" pyinstaller

echo "==> building FDE Scope.app v$VERSION"
"$VENV/bin/pyinstaller" appbuild/FDEScope.spec \
  --distpath appbuild/dist --workpath appbuild/build --clean --noconfirm

APP="appbuild/dist/FDE Scope.app"
DMG="appbuild/dist/FDE-Scope-$VERSION.dmg"
STAGE=appbuild/dist/dmg-stage

echo "==> packaging DMG → $DMG"
rm -rf "$STAGE" "$DMG"; mkdir -p "$STAGE"
mv "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "FDE Scope" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
mv "$STAGE/FDE Scope.app" "appbuild/dist/"
rm -rf "$STAGE"

echo
echo "done:"
echo "  app: $APP   (double-click to run)"
echo "  dmg: $DMG   (share/distribute)"
