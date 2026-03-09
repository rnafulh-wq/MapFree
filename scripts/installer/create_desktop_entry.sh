#!/usr/bin/env bash
# Create MapFree desktop entry and icon for app launcher.
# Usage: create_desktop_entry.sh <path-to-MapFree-executable> [path-to-icon.png]
# Example: create_desktop_entry.sh ~/.local/bin/mapfree.AppImage

set -e

EXEC_PATH="${1:?Path to MapFree executable required}"
EXEC_PATH="$(readlink -f "$EXEC_PATH" 2>/dev/null || realpath "$EXEC_PATH" 2>/dev/null || echo "$EXEC_PATH")"
ICON_PATH="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEFAULT_ICON="$REPO_ROOT/mapfree/gui/resources/icons/mapfree.png"

DESKTOP_DIR="${HOME}/.local/share/applications"
ICONS_DIR="${HOME}/.local/share/icons"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICONS_DIR"

if [[ -z "$ICON_PATH" && -f "$DEFAULT_ICON" ]]; then
  ICON_PATH="$DEFAULT_ICON"
fi
ICON_FILE=""
if [[ -n "$ICON_PATH" && -f "$ICON_PATH" ]]; then
  cp "$ICON_PATH" "$ICONS_DIR/mapfree.png"
  ICON_FILE="$ICONS_DIR/mapfree.png"
fi

if [[ -n "$ICON_FILE" ]]; then
  ICON_LINE="Icon=$ICON_FILE"
else
  ICON_LINE="Icon=mapfree"
fi

cat > "$DESKTOP_DIR/mapfree.desktop" << EOF
[Desktop Entry]
Type=Application
Name=MapFree Engine
Comment=Photogrammetry pipeline engine (COLMAP + OpenMVS)
Exec=$EXEC_PATH
$ICON_LINE
Categories=Graphics;Science;
EOF

if command -v update-desktop-database &>/dev/null; then
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "Desktop entry: $DESKTOP_DIR/mapfree.desktop"
echo "Icon: $ICONS_DIR/mapfree.png (jika ada)"
