"""Barcode/QR detection for item routing: a decodable code means packaged
goods (see product_lookup.py); no code means the produce flow.

Wraps the `arduino:camera_code_detection` brick, which scans the live camera
feed continuously on its own thread and fires `on_detect(frame, detection)`
whenever it reads a code. That's asynchronous, while the checkout pipeline
asks its question at one specific moment -- when the weight settles -- so
this class remembers what has been seen for the item currently on the scale
and forgets it on `on_item_reset()`, which main.py calls when the scale
returns to zero between items. A code spotted while the shopper was still
setting the item down therefore still counts when the weight settles a
moment later.
"""
import threading
from dataclasses import dataclass

import numpy as np


@dataclass
class CodeDetection:
    value: str
    symbology: str


class CodeDetector:
    def __init__(self, camera=None):
        from arduino.app_bricks.camera_code_detection import CameraCodeDetection

        self._lock = threading.Lock()
        self._current: CodeDetection | None = None
        self._detector = (
            CameraCodeDetection(camera=camera) if camera is not None else CameraCodeDetection()
        )
        self._detector.on_detect(self._on_detect)

    def _on_detect(self, frame, detection) -> None:
        with self._lock:
            self._current = CodeDetection(value=detection.content, symbology=detection.type)

    def start(self) -> None:
        self._detector.start()

    def on_item_reset(self) -> None:
        """Forget the code read for the item that just left the scale."""
        with self._lock:
            self._current = None

    def get_current_detection(self, frame: np.ndarray | None = None) -> CodeDetection | None:
        """The code seen for the item currently on the scale, if any.

        `frame` is accepted so callers can pass the frame that triggered the
        scan, but the answer comes from the continuous scan rather than a
        one-shot decode of that single frame.
        """
        with self._lock:
            return self._current


def get_code_detector(camera=None) -> CodeDetector:
    return CodeDetector(camera)
