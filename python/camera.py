"""Still-frame capture from the checkout-scale webcam.

Wraps `arduino.app_peripherals.camera.V4LCamera`, which handles device
discovery and auto-reconnect and hands back numpy BGR arrays -- the same
layout OpenCV produces, so ocr.py and the rest of the pipeline take frames
from here unchanged.
"""
import numpy as np


class Camera:
    def __init__(self, device_index: int = 0):
        from arduino.app_peripherals.camera import V4LCamera

        self._camera = V4LCamera(device=device_index)
        self._camera.start()

    @property
    def raw(self):
        """The underlying V4LCamera, shared with the code detector so the
        one physical webcam is opened once rather than per consumer."""
        return self._camera

    def capture(self) -> np.ndarray:
        frame = self._camera.capture()
        if frame is None:
            raise RuntimeError("Failed to capture frame from webcam")
        return frame


def get_camera() -> Camera:
    return Camera()
