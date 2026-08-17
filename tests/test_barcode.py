import json
from pathlib import Path

import cv2
import pytest

from app.vision.barcode import decode_first_barcode

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "barcodes"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text())


@pytest.mark.parametrize("filename,ground_truth", MANIFEST.items())
def test_decode_barcode_on_fixture(filename, ground_truth):
    image = cv2.imread(str(FIXTURE_DIR / filename))
    result = decode_first_barcode(image)
    assert result is not None, f"No barcode decoded in {filename}"
    assert result.value == ground_truth
