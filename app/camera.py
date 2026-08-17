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
    def __init__(self, device_index: int = 0):
        self._capture = cv2.VideoCapture(device_index)

    def capture(self) -> np.ndarray:
        ok, frame = self._capture.read()
        if not ok:
            raise RuntimeError("Failed to capture frame from webcam")
        return frame


def get_camera() -> Camera:
    if SIMULATE_HARDWARE:
        fixtures = [p for d in DEFAULT_FIXTURE_DIRS for p in sorted(d.glob("*.png"))]
        return SimulatedCamera(fixtures)
    return WebcamCamera()
