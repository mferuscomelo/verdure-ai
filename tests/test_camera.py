import cv2
import numpy as np
import pytest

import camera


@pytest.fixture
def fixture_images(tmp_path):
    paths = []
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        path = tmp_path / f"item_{i}.png"
        image = np.full((10, 10, 3), color, dtype=np.uint8)
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths


def test_simulated_camera_returns_image_array(fixture_images):
    cam = camera.SimulatedCamera(fixture_images)
    frame = cam.capture()
    assert frame.shape == (10, 10, 3)


def test_simulated_camera_cycles_through_fixtures_in_order(fixture_images):
    cam = camera.SimulatedCamera(fixture_images)
    first = cam.capture()
    second = cam.capture()
    assert not np.array_equal(first, second)


def test_simulated_camera_wraps_around_after_last_fixture(fixture_images):
    cam = camera.SimulatedCamera(fixture_images)
    seen = [cam.capture() for _ in range(len(fixture_images))]
    wrapped = cam.capture()
    assert np.array_equal(wrapped, seen[0])


def test_simulated_camera_raises_on_empty_fixture_list():
    with pytest.raises(ValueError):
        camera.SimulatedCamera([])
