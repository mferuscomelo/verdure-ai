"""Throwaway pass-rate/latency report for barcode decode across rotations."""
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.vision.barcode import decode_first_barcode  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "barcodes"
manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())

results = []
for filename, gt in manifest.items():
    image = cv2.imread(str(FIXTURE_DIR / filename))
    start = time.perf_counter()
    result = decode_first_barcode(image)
    elapsed_ms = (time.perf_counter() - start) * 1000
    value = result.value if result else None
    results.append((filename, gt, value, elapsed_ms, value == gt))

print(f"{'file':<16} {'ground truth':<14} {'decoded':<14} {'ms':>7}  ok")
print("-" * 60)
n_pass = 0
for filename, gt, value, ms, passed in results:
    n_pass += passed
    print(f"{filename:<16} {gt:<14} {str(value):<14} {ms:7.1f}  {'PASS' if passed else 'FAIL'}")
print("-" * 60)
print(f"{n_pass}/{len(results)} passed ({100*n_pass/len(results):.0f}%)")
avg_ms = sum(r[3] for r in results) / len(results)
print(f"avg latency: {avg_ms:.1f} ms/image (this laptop's CPU)")
