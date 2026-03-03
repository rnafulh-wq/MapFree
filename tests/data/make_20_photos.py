#!/usr/bin/env python3
"""Buat 20 file JPEG minimal valid untuk uji mapfree (tanpa dependency)."""
from pathlib import Path

# Minimal valid 1x1 JPEG (125 bytes, JFIF)
MINIMAL_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010101004800480000"
    "ffdb004300030202020202020303020202030303030304060404040404080606050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010"
    "ffc9000b0800010001011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)

def main():
    out = Path(__file__).resolve().parent / "run_20photos"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(1, 21):
        (out / f"img_{i:02d}.jpg").write_bytes(MINIMAL_JPEG)
    print(f"Created 20 JPEGs in {out}")

if __name__ == "__main__":
    main()
