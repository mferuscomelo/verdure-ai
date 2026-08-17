"""Best-by / expiry date extraction from a captured product image.

Runs RapidOCR (ONNX Runtime build of PP-OCR, a scene-text detector+recognizer)
over the raw captured frame and parses the detected text for a date in one of
the common formats printed on packaged goods. Designed to run fully offline
on the UNO Q's MPU (no GPU, no network calls).

Scene text (a photo of a real product: curved/reflective surfaces, skewed
labels, busy backgrounds) is a different problem from the scanned-document
text Tesseract is built for -- an earlier Tesseract + hand-rolled
deskew/threshold pipeline read 10/10 synthetic label fixtures but 0/6 real
photos even after adding region localization. RapidOCR's detector finds and
orients text regions itself, so it's fed the raw frame directly -- no manual
crop/deskew/threshold step.
"""
import calendar
import re
from dataclasses import dataclass
from datetime import date

import numpy as np
from rapidocr_onnxruntime import RapidOCR

MONTHS = (
    "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC"
    "|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
)

# Ordered by specificity; first match wins.
DATE_PATTERNS = [
    # 2027-01-09 (ISO)
    (re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b"), "ymd"),
    # 21 MAR 2027 / 21-MAR-2027 / 21MAR2027 (OCR sometimes drops separators)
    (re.compile(rf"\b(\d{{1,2}})[\s\-]?({MONTHS})[\s\-]?(\d{{4}})\b", re.IGNORECASE), "dmon_y"),
    # 08/15/2027 or 08-15-2027. Tried as MM/DD/YYYY (US-style) first, falling back to
    # DD/MM/YYYY (common on European packaging, e.g. Open Food Facts source products)
    # when the first interpretation isn't a real date.
    (re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"), "mdy"),
    # 12/2026 (month/year only, no day -- common on long-shelf-life packaged goods).
    # Resolves to the last day of that month, matching "best if used by end of month".
    (re.compile(r"\b(\d{1,2})/(\d{4})\b"), "my"),
]

_MONTH_LOOKUP = {name[:3]: i for i, name in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1
)}


@dataclass
class DateExtractionResult:
    raw_text: str
    parsed_date: date | None
    matched_substring: str | None


_engine: RapidOCR | None = None


def _get_engine() -> RapidOCR:
    """Lazily construct the OCR engine (loading the ONNX models is slow enough
    that we don't want it to happen at import time, e.g. for unrelated tests)."""
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def _text_height(box: list) -> float:
    """RapidOCR boxes are 4-point quads that follow the text's own rotation, not
    axis-aligned. A skewed/curved label's *axis-aligned* bbox height balloons
    with rotation (e.g. a 20deg-tilted 55px-tall line reports ~195px), which
    makes it useless as a same-row tolerance. The quad's own short-side length
    is the actual line thickness regardless of rotation."""
    pts = np.array(box)
    sides = sorted(np.linalg.norm(pts[i] - pts[(i + 1) % 4]) for i in range(4))
    return (sides[0] + sides[1]) / 2


def _cluster_lines(ocr_result: list) -> str:
    """RapidOCR returns one (box, text, score) tuple per detected text region,
    not necessarily in reading order. Group boxes into visual rows (by y-center
    proximity relative to true text height) and sort each row left-to-right, so
    a date split across several detected boxes (e.g. "05" "SEP" "2026")
    reassembles in the right order for the regex patterns below to match."""
    if not ocr_result:
        return ""

    items = []
    for box, text, _score in ocr_result:
        ys = [point[1] for point in box]
        xs = [point[0] for point in box]
        items.append({"y": sum(ys) / len(ys), "x": min(xs), "h": _text_height(box), "text": text})
    items.sort(key=lambda item: item["y"])

    rows = [[items[0]]]
    for item in items[1:]:
        row_gap = abs(item["y"] - rows[-1][-1]["y"])
        if row_gap <= 0.6 * max(rows[-1][-1]["h"], item["h"]):
            rows[-1].append(item)
        else:
            rows.append([item])

    return "\n".join(" ".join(i["text"] for i in sorted(row, key=lambda i: i["x"])) for row in rows)


def _parse_match(match: re.Match, kind: str) -> date | None:
    try:
        if kind == "ymd":
            y, m, d = match.groups()
            return date(int(y), int(m), int(d))
        if kind == "mdy":
            a, b, y = match.groups()
            try:
                return date(int(y), int(a), int(b))  # MM/DD/YYYY
            except ValueError:
                return date(int(y), int(b), int(a))  # fall back to DD/MM/YYYY
        if kind == "dmon_y":
            d, mon, y = match.groups()
            month = _MONTH_LOOKUP.get(mon[:3].upper())
            if not month:
                return None
            return date(int(y), month, int(d))
        if kind == "my":
            m, y = match.groups()
            m, y = int(m), int(y)
            last_day = calendar.monthrange(y, m)[1]
            return date(y, m, last_day)
    except ValueError:
        return None
    return None


def extract_date(raw_text: str) -> DateExtractionResult:
    # OCR occasionally inserts a stray space inside what should be one
    # contiguous digit run (e.g. "20 27" for "2027"); collapsing those before
    # matching recovers the date without weakening the patterns themselves.
    # Hyphens are left alone -- they're a legitimate date separator (ISO
    # dates, "08-15-2027") that the patterns above rely on being present.
    # Only same-line whitespace is collapsed: a newline is a real boundary
    # between unrelated fields (e.g. a barcode digit run above the date line),
    # and collapsing across it would erase the word boundary the patterns need.
    normalized = re.sub(r"(?<=\d)[ \t]+(?=\d)", "", raw_text.upper())
    for pattern, kind in DATE_PATTERNS:
        match = pattern.search(normalized)
        if match:
            parsed = _parse_match(match, kind)
            if parsed:
                return DateExtractionResult(raw_text, parsed, match.group(0))
    return DateExtractionResult(raw_text, None, None)


def read_best_by_date(image: np.ndarray) -> DateExtractionResult:
    """Full pipeline: OCR the raw captured frame -> reassemble reading order -> parse.
    `image` is a BGR array (as from OpenCV)."""
    result, _elapsed = _get_engine()(image)
    text = _cluster_lines(result)
    return extract_date(text)
