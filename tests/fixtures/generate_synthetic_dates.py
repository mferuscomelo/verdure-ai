"""Generates synthetic best-by/expiry date label images for OCR testing.

Not part of the shipped app — a throwaway fixture generator for the OCR
feasibility spike. Produces a mix of print styles (clean label, dot-matrix
stamp, low-contrast, rotated, blurry) with known ground-truth dates, plus
a manifest.json mapping filename -> ground truth date string.
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).parent / "best_by_dates"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path("/usr/share/fonts/truetype")
CLEAN_FONT = FONT_DIR / "dejavu/DejaVuSansMono-Bold.ttf"
STAMP_FONT = FONT_DIR / "dejavu/DejaVuSansMono.ttf"

random.seed(42)


def base_canvas(w=500, h=220, bg=(235, 230, 220)):
    img = Image.new("RGB", (w, h), bg)
    return img


def draw_label(text, font_path, font_size, fg=(20, 20, 20), bg=(235, 230, 220), noise=0, blur=0, rotate=0, jitter=0):
    img = base_canvas(bg=bg)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(font_path), font_size)

    prefix = random.choice(["BEST BY", "BEST BEFORE", "EXP", "USE BY", ""])
    full_text = f"{prefix}\n{text}" if prefix else text

    y = 60
    for line in full_text.split("\n"):
        x = 40
        for ch in line:
            dx = random.randint(-jitter, jitter) if jitter else 0
            dy = random.randint(-jitter, jitter) if jitter else 0
            draw.text((x + dx, y + dy), ch, font=font, fill=fg)
            x += font.getlength(ch) + random.randint(0, 2)
        y += font_size + 20

    if noise:
        import numpy as np

        arr = np.array(img).astype(int)
        speckle = np.random.randint(-noise, noise, arr.shape)
        arr = np.clip(arr + speckle, 0, 255).astype("uint8")
        img = Image.fromarray(arr)

    if rotate:
        img = img.rotate(rotate, expand=True, fillcolor=bg)

    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))

    return img


CASES = [
    # (filename, ground_truth_date, kwargs)
    ("clean_slash.png", "08/15/2027", dict(font_path=CLEAN_FONT, font_size=34)),
    ("clean_iso.png", "2026-11-30", dict(font_path=CLEAN_FONT, font_size=34)),
    ("clean_dmon.png", "05 SEP 2026", dict(font_path=CLEAN_FONT, font_size=30)),
    ("dotmatrix_stamp.png", "12/01/2026", dict(font_path=STAMP_FONT, font_size=30, fg=(90, 40, 30), jitter=2)),
    ("dotmatrix_faint.png", "03/22/2027", dict(font_path=STAMP_FONT, font_size=28, fg=(150, 150, 150), jitter=2)),
    ("low_contrast.png", "2027-01-09", dict(font_path=CLEAN_FONT, font_size=32, fg=(180, 178, 170))),
    ("noisy.png", "09/09/2026", dict(font_path=CLEAN_FONT, font_size=34, noise=35)),
    ("rotated_5deg.png", "21 MAR 2027", dict(font_path=CLEAN_FONT, font_size=32, rotate=5)),
    ("rotated_neg8deg.png", "10/10/2026", dict(font_path=CLEAN_FONT, font_size=34, rotate=-8)),
    ("blurry.png", "2026-12-25", dict(font_path=CLEAN_FONT, font_size=34, blur=1.6)),
]

manifest = {}
for filename, gt_date, kwargs in CASES:
    img = draw_label(gt_date, **kwargs)
    img.save(OUT_DIR / filename)
    manifest[filename] = gt_date

with open(OUT_DIR / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f"Generated {len(CASES)} synthetic fixtures in {OUT_DIR}")
