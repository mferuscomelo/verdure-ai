import json
from pathlib import Path

import cv2
import pytest

from code_detector import SimulatedCodeDetector, decode_first_barcode

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "barcodes"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text())


@pytest.mark.parametrize("filename,ground_truth", MANIFEST.items())
def test_decode_barcode_on_fixture(filename, ground_truth):
    image = cv2.imread(str(FIXTURE_DIR / filename))
    result = decode_first_barcode(image)
    assert result is not None, f"No barcode decoded in {filename}"
    assert result.value == ground_truth


def test_simulated_code_detector_decodes_current_frame():
    image = cv2.imread(str(FIXTURE_DIR / "rot_000.png"))
    detector = SimulatedCodeDetector()
    result = detector.get_current_detection(image)
    assert result is not None
    assert result.value == "070970474088"


def test_simulated_code_detector_returns_none_without_a_frame():
    detector = SimulatedCodeDetector()
    assert detector.get_current_detection(None) is None
