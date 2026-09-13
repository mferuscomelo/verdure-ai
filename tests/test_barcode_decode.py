"""Rotation tolerance of the bench decoder against the fixture corpus.

The fixtures are one real product photo rotated through 0, +/-5, +/-15, 90,
180 and 270 degrees, which is the range a shopper's hand realistically puts
a barcode through.
"""
import json
from pathlib import Path

import cv2
import pytest

from tools.barcode_decode import decode_barcodes, decode_first_barcode

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "barcodes"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text())


@pytest.mark.parametrize("filename,ground_truth", MANIFEST.items())
def test_decode_barcode_on_fixture(filename, ground_truth):
    image = cv2.imread(str(FIXTURE_DIR / filename))
    result = decode_first_barcode(image)
    assert result is not None, f"No barcode decoded in {filename}"
    assert result.value == ground_truth


def test_decode_reports_the_symbology_and_location():
    image = cv2.imread(str(FIXTURE_DIR / "rot_000.png"))

    results = decode_barcodes(image)

    assert len(results) == 1
    assert results[0].symbology in {"UPCA", "EAN13"}
    assert results[0].rect is not None


def test_decode_returns_nothing_for_an_image_with_no_barcode():
    image = cv2.imread(
        str(Path(__file__).parent / "fixtures" / "best_by_dates" / "clean_iso.png")
    )

    assert decode_first_barcode(image) is None
