import json
from datetime import date
from pathlib import Path

import cv2
import pytest

from ocr import extract_date, read_best_by_date

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "best_by_dates"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text())


@pytest.mark.parametrize("filename,ground_truth", MANIFEST.items())
def test_read_best_by_date_on_fixture(filename, ground_truth):
    image = cv2.imread(str(FIXTURE_DIR / filename))
    expected = extract_date(ground_truth.upper()).parsed_date
    result = read_best_by_date(image)
    assert result.parsed_date == expected, (
        f"OCR raw text was: {result.raw_text!r}"
    )


@pytest.mark.parametrize(
    "raw_text,expected",
    [
        ("BEST BY\n08/15/2027", date(2027, 8, 15)),
        ("EXP 2026-11-30", date(2026, 11, 30)),
        ("21 MAR 2027", date(2027, 3, 21)),
        ("no date here at all", None),
        ("13/45/2027", None),  # not a real date, should not parse
        ("22/01/2029", date(2029, 1, 22)),  # DD/MM/YYYY: invalid as MM/DD (month 22), falls back
        ("MHD: 12/2026", date(2026, 12, 31)),  # month/year only -> resolves to end of month
        ("03/22/20 27", date(2027, 3, 22)),  # OCR sometimes inserts a stray space within a digit run
    ],
)
def test_extract_date_from_text(raw_text, expected):
    assert extract_date(raw_text).parsed_date == expected
