"""Generates rotated variants of a real product-photo barcode fixture.

Not part of the shipped app — a throwaway fixture generator, same pattern as
generate_synthetic_dates.py, but rotates one real photo (source/candy_box_original.jpg)
instead of synthesizing text. Angle set: full-turn (90/180/270) for robustness across
arbitrary mounting orientation, plus small handheld-tilt skews (+-5, +-15) mirroring
ocr.py's deskew range — unlike ocr.py, barcode.py has no deskew step, so this is what
actually exercises pyzbar/zbar's own rotation tolerance.
"""
import json
from pathlib import Path

from PIL import Image

SOURCE_IMAGE = Path(__file__).parent / "barcodes" / "source" / "candy_box_original.jpg"
OUT_DIR = Path(__file__).parent / "barcodes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GROUND_TRUTH_BARCODE = "070970474088"

ROTATIONS = {
    "rot_000.png": 0,
    "rot_p005.png": 5,
    "rot_n005.png": -5,
    "rot_p015.png": 15,
    "rot_n015.png": -15,
    "rot_090.png": 90,
    "rot_180.png": 180,
    "rot_270.png": 270,
}

img = Image.open(SOURCE_IMAGE).convert("RGB")
bg = img.getpixel((0, 0))  # corner sample, used as fill for the expanded canvas

manifest = {}
for filename, angle in ROTATIONS.items():
    rotated = img.rotate(angle, expand=True, fillcolor=bg) if angle else img
    rotated.save(OUT_DIR / filename)
    manifest[filename] = GROUND_TRUTH_BARCODE

with open(OUT_DIR / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f"Generated {len(ROTATIONS)} barcode rotation fixtures in {OUT_DIR}")
