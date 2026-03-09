"""Convert MapFree taskbar logo from PNG to ICO for Inno Setup.

Run from repo root or via: python scripts/installer/png_to_ico.py
Requires: pip install Pillow
"""
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit("PIL/Pillow required: pip install Pillow")

# Standard ICO sizes for installer/taskbar
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def png_to_ico(png_path: str, ico_path: str) -> None:
    """Convert a PNG image to multi-size ICO."""
    img = Image.open(png_path)
    img.save(ico_path, format="ICO", sizes=ICO_SIZES)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent
    png = root / "assets" / "MapFree_logo_taskbar.png"
    ico = root / "assets" / "MapFree_logo_taskbar.ico"
    if not png.exists():
        raise SystemExit(f"Source PNG not found: {png}")
    png_to_ico(str(png), str(ico))
    print(f"Created: {ico}")
