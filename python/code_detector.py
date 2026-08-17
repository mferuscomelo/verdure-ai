"""Barcode/QR detection for the item-routing pipeline: a decodable code means
packaged goods (see product_lookup.py); no code means the produce flow.

Follows the same SIMULATE_HARDWARE Simulated/Hardware split as
bridge_client.py and camera.py:

- `SimulatedCodeDetector` decodes a captured frame directly with pyzbar
  (zbar backend), synchronously, on demand -- today's exact behavior, kept
  as real production code for the simulated path (and reused by
  tools/barcode_debug_server.py), not just test fixture material.
- `HardwareCodeDetector` wraps the `arduino:camera_code_detection` brick,
  which scans the live camera feed continuously in the background and fires
  `on_detect(frame, detection)` asynchronously on its own thread -- a
  fundamentally different shape than a single decode-on-demand call. It
  tracks whatever's been seen since the last `on_item_reset()` (called when
  the scale's weight returns to ~0g between items) so `get_current_detection()`
  can hand back the right answer once weight goes stable, regardless of
  exactly when the code was scanned during the item's time on the scale.
"""
import os
import threading
from dataclasses import dataclass

import cv2
import numpy as np
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

SIMULATE_HARDWARE = os.environ.get("SIMULATE_HARDWARE") == "1"

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


class CodeDetector:
    """Common interface router.py/checkout.py use, regardless of which
    implementation is active: whatever the current item on the scale is,
    has a barcode/QR been seen for it yet?"""

    def start(self) -> None:
        raise NotImplementedError

    def on_item_reset(self) -> None:
        """Call when weight returns to ~0g between items, to clear any
        detection accumulated for the item that just left the scale."""
        raise NotImplementedError

    def get_current_detection(self, frame: np.ndarray | None) -> BarcodeResult | None:
        raise NotImplementedError


class SimulatedCodeDetector(CodeDetector):
    def start(self) -> None:
        pass

    def on_item_reset(self) -> None:
        pass

    def get_current_detection(self, frame: np.ndarray | None) -> BarcodeResult | None:
        return decode_first_barcode(frame) if frame is not None else None


class HardwareCodeDetector(CodeDetector):
    def __init__(self, camera=None):
        from arduino.app_bricks.camera_code_detection import CameraCodeDetection  # only importable in the App Lab container

        self._lock = threading.Lock()
        self._latest: BarcodeResult | None = None
        self._detector = CameraCodeDetection(camera=camera) if camera is not None else CameraCodeDetection()
        self._detector.on_detect(self._on_detect)

    def _on_detect(self, frame, detection) -> None:
        with self._lock:
            self._latest = BarcodeResult(value=detection.content, symbology=detection.type, rect=None)

    def start(self) -> None:
        self._detector.start()

    def on_item_reset(self) -> None:
        with self._lock:
            self._latest = None

    def get_current_detection(self, frame: np.ndarray | None) -> BarcodeResult | None:
        with self._lock:
            return self._latest


def get_code_detector(camera=None) -> CodeDetector:
    if SIMULATE_HARDWARE:
        return SimulatedCodeDetector()
    return HardwareCodeDetector(camera)
