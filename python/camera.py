"""Frame capture from the checkout-scale webcam, with a SIMULATE_HARDWARE
fallback that cycles through fixture images so vision code is testable
headlessly.
"""
import os
from pathlib import Path

import cv2
import numpy as np

SIMULATE_HARDWARE = os.environ.get("SIMULATE_HARDWARE") == "1"

DEFAULT_FIXTURE_DIRS = [
    Path(__file__).parent.parent / "tests" / "fixtures" / "barcodes",
    Path(__file__).parent.parent / "tests" / "fixtures" / "best_by_dates",
]


class Camera:
    def capture(self) -> np.ndarray:
        raise NotImplementedError

    @property
    def raw(self):
        """The underlying real camera object, if any -- shared with
        HardwareCodeDetector so the USB webcam isn't opened twice.
        None for SimulatedCamera."""
        return None


class SimulatedCamera(Camera):
    """Cycles through a fixed list of fixture images in order, one per
    capture() call, wrapping around at the end -- stands in for a shopper
    presenting a sequence of items to the scale's webcam.
    """

    def __init__(self, fixture_paths: list[Path]):
        if not fixture_paths:
            raise ValueError("SimulatedCamera needs at least one fixture image")
        self._fixture_paths = list(fixture_paths)
        self._index = 0

    def capture(self) -> np.ndarray:
        path = self._fixture_paths[self._index % len(self._fixture_paths)]
        self._index += 1
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(f"Could not read fixture image: {path}")
        return image


class WebcamCamera(Camera):
    """Wraps `arduino.app_peripherals.camera.Camera` (V4L) instead of raw
    `cv2.VideoCapture` -- App Lab already handles device discovery and
    auto-reconnect, and it returns numpy BGR arrays just like OpenCV did, so
    downstream code (ocr.py, code_detector.py) needs no change. Lazily
    imported, matching HardwareBridgeClient's pattern, so this class is only
    ever instantiated (and only then needs `arduino.*` installed) when
    SIMULATE_HARDWARE is off.
    """

    def __init__(self, device_index: int = 0):
        # V4LCamera (not the Camera factory) since its constructor kwargs are
        # fully documented; the factory's aren't.
        from arduino.app_peripherals.camera import V4LCamera

        self._camera = V4LCamera(device=device_index)
        self._camera.start()

    @property
    def raw(self):
        return self._camera

    def capture(self) -> np.ndarray:
        frame = self._camera.capture()
        if frame is None:
            raise RuntimeError("Failed to capture frame from webcam")
        return frame


def get_camera() -> Camera:
    if SIMULATE_HARDWARE:
        fixtures = [p for d in DEFAULT_FIXTURE_DIRS for p in sorted(d.glob("*.png"))]
        return SimulatedCamera(fixtures)
    return WebcamCamera()
