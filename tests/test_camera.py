from unittest.mock import Mock

import numpy as np
import pytest

import camera

FRAME = np.full((4, 4, 3), 128, dtype=np.uint8)


def _v4l(frame=FRAME):
    return Mock(capture=Mock(return_value=frame), start=Mock())


def test_camera_starts_the_device_on_construction(arduino):
    device = _v4l()
    arduino.v4l_camera_cls = lambda **kwargs: device

    camera.get_camera()

    device.start.assert_called_once()


def test_capture_returns_the_frame_as_a_numpy_array(arduino):
    arduino.v4l_camera_cls = lambda **kwargs: _v4l()

    frame = camera.get_camera().capture()

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (4, 4, 3)


def test_capture_raises_when_the_device_yields_no_frame(arduino):
    arduino.v4l_camera_cls = lambda **kwargs: _v4l(frame=None)

    with pytest.raises(RuntimeError):
        camera.get_camera().capture()


def test_raw_exposes_the_device_for_sharing_with_the_code_detector(arduino):
    device = _v4l()
    arduino.v4l_camera_cls = lambda **kwargs: device

    assert camera.get_camera().raw is device
