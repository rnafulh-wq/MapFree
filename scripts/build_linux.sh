#!/usr/bin/env bash
# Build MapFree as a Linux AppImage.
# Run from repo root: ./scripts/build_linux.sh
# Requires: PyInstaller, fuse (for running the resulting AppImage).
# Output: dist/MapFree-x86_64.AppImage

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "[1/5] Running PyInstaller..."
pyinstaller scripts/build_linux.spec --clean --noconfirm

DIST_APP="$ROOT/dist/MapFree"
APPDIR="$ROOT/dist/MapFree.AppDir"
APPIMAGETOOL="$ROOT/scripts/appimagetool-x86_64.AppImage"
ICON_SRC="$ROOT/mapfree/gui/resources/icons/mapfree.png"

if [[ ! -d "$DIST_APP" ]]; then
  echo "Expected PyInstaller output at $DIST_APP" >&2
  exit 1
fi

echo "[2/5] Creating AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR"
cp -a "$DIST_APP"/* "$APPDIR"/

echo "[3/5] Adding AppRun and desktop file..."
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/MapFree" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/MapFree.desktop" << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=MapFree
Comment=Photogrammetry pipeline engine (COLMAP + OpenMVS)
Exec=MapFree
Icon=mapfree
Categories=Graphics;Science;
DESKTOP

if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$APPDIR/mapfree.png"
else
  echo "Warning: $ICON_SRC not found; AppImage will have no icon." >&2
fi

echo "[4/5] Downloading appimagetool if needed..."
if [[ ! -x "$APPIMAGETOOL" ]]; then
  URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  if command -v curl &>/dev/null; then
    curl -sL -o "$APPIMAGETOOL" "$URL"
  elif command -v wget &>/dev/null; then
    wget -q -O "$APPIMAGETOOL" "$URL"
  else
    echo "Need curl or wget to download appimagetool." >&2
    exit 1
  fi
  chmod +x "$APPIMAGETOOL"
fi

echo "[5/5] Building AppImage..."
OUTPUT="$ROOT/dist/MapFree-x86_64.AppImage"
# Run in dist/ so appimagetool sees ARCH; optional: export ARCH=x86_64
(cd "$ROOT/dist" && ARCH=x86_64 "$APPIMAGETOOL" MapFree.AppDir MapFree-x86_64.AppImage)

echo "Done: $OUTPUT"
echo "Run: $OUTPUT"
