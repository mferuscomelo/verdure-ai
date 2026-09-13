"""Throwaway report script for the OCR feasibility spike.

Runs ocr.read_best_by_date against every fixture in best_by_dates/,
compares to the ground-truth manifest, and prints a pass-rate summary
plus per-image timing.
"""
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
from ocr import extract_date, read_best_by_date  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "best_by_dates"
manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())

results = []
for filename, gt_str in manifest.items():
    img = cv2.imread(str(FIXTURE_DIR / filename))
    start = time.perf_counter()
    result = read_best_by_date(img)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # ground truth strings in manifest are the *rendered* text, not necessarily
    # a fixed format -- reparse loosely by reusing our own extractor on the gt string.
    gt_parsed = extract_date(gt_str.upper()).parsed_date

    passed = result.parsed_date == gt_parsed
    results.append((filename, gt_str, gt_parsed, result.parsed_date, result.matched_substring, elapsed_ms, passed))

print(f"{'file':<22} {'ground truth':<14} {'parsed':<12} {'match text':<14} {'ms':>7}  ok")
print("-" * 80)
n_pass = 0
for filename, gt_str, gt_parsed, parsed, match_text, ms, passed in results:
    n_pass += passed
    mark = "PASS" if passed else "FAIL"
    print(f"{filename:<22} {gt_str:<14} {str(parsed):<12} {str(match_text):<14} {ms:7.1f}  {mark}")

print("-" * 80)
print(f"{n_pass}/{len(results)} passed ({100*n_pass/len(results):.0f}%)")
avg_ms = sum(r[5] for r in results) / len(results)
print(f"avg latency: {avg_ms:.1f} ms/image (this laptop's CPU)")
