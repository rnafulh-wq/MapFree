"""
Convert MapFree taskbar PNG to ICO for Inno Setup.

Run from repo root: python scripts/installer/png_to_ico.py
Requires: Pillow. Output: assets/MapFree_logo_taskbar.ico
"""

from pathlib import Path


def main() -> None:
    repo = Path(__file__).resolve().parent.parent.parent
    png = repo / "assets" / "MapFree_logo_taskbar.png"
    ico = repo / "assets" / "MapFree_logo_taskbar.ico"
    if not png.is_file():
        print("Skip ICO: %s not found" % png)
        return
    try:
        from PIL import Image
    except ImportError:
        print("Pillow required: pip install Pillow")
        raise SystemExit(1)
    img = Image.open(png)
    img.save(ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print("Wrote %s" % ico)


if __name__ == "__main__":
    main()
