"""Still-image barcode decoding, used by the debug server below.

The kiosk itself reads codes from the live camera feed through the
`camera_code_detection` brick (see python/code_detector.py). This module is
the bench equivalent: point it at a photo and it tells you what zbar makes
of it, which is how the fixture corpus in tests/fixtures/barcodes/ was
checked for rotation tolerance.
"""
from dataclasses import dataclass

import cv2
import numpy as np
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

SUPPORTED_SYMBOLS = [
    ZBarSymbol.EAN13, ZBarSymbol.UPCA, ZBarSymbol.EAN8, ZBarSymbol.UPCE,
    ZBarSymbol.CODE128,
]


@dataclass
class BarcodeResult:
    value: str
    symbology: str
    rect: tuple[int, int, int, int] | None


def _normalize_upca(symbology: str, value: str) -> str:
    """zbar reports a 12-digit UPC-A as a 13-digit EAN-13 with a leading 0
    (well-known zbar quirk); strip it so UPC-A values are consistently 12 digits."""
    if symbology == "EAN13" and len(value) == 13 and value.startswith("0"):
        return value[1:]
    return value


def decode_barcodes(image: np.ndarray) -> list[BarcodeResult]:
    """`image` is a BGR array (as from OpenCV). Returns [] if nothing decodes."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    decoded = pyzbar.decode(gray, symbols=SUPPORTED_SYMBOLS)
    results = []
    for d in decoded:
        symbology = d.type
        value = _normalize_upca(symbology, d.data.decode("utf-8", errors="replace"))
        results.append(BarcodeResult(
            value=value, symbology=symbology,
            rect=(d.rect.left, d.rect.top, d.rect.width, d.rect.height),
        ))
    return results


def decode_first_barcode(image: np.ndarray) -> BarcodeResult | None:
    results = decode_barcodes(image)
    return results[0] if results else None
