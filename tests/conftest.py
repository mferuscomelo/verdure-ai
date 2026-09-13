"""Stand-ins for the `arduino.*` packages that only exist inside the App Lab
container on the board.

bridge_client, camera, code_detector and produce_classifier each import
their dependency inside `__init__` rather than at module scope, so the
wrappers around them can be constructed and exercised here with the real
packages absent -- which is what lets the wiring be tested off the bench.
"""
import sys
import types

import pytest


class _FakeModules:
    """Handles onto the injected stubs, so tests can set return values and
    assert on the calls the wrappers made."""

    def __init__(self):
        self.bridge = types.SimpleNamespace(call=None)
        self.v4l_camera_cls = None
        self.code_detection_cls = None
        self.image_classification_cls = None


@pytest.fixture
def arduino(monkeypatch):
    fakes = _FakeModules()

    def install(name: str) -> types.ModuleType:
        module = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    arduino_pkg = install("arduino")

    app_utils = install("arduino.app_utils")
    app_utils.Bridge = fakes.bridge
    arduino_pkg.app_utils = app_utils

    peripherals = install("arduino.app_peripherals")
    camera_mod = install("arduino.app_peripherals.camera")
    camera_mod.V4LCamera = lambda **kwargs: fakes.v4l_camera_cls(**kwargs)
    peripherals.camera = camera_mod
    arduino_pkg.app_peripherals = peripherals

    bricks = install("arduino.app_bricks")
    detection_mod = install("arduino.app_bricks.camera_code_detection")
    detection_mod.CameraCodeDetection = lambda **kwargs: fakes.code_detection_cls(**kwargs)
    classification_mod = install("arduino.app_bricks.image_classification")
    classification_mod.ImageClassification = lambda **kwargs: fakes.image_classification_cls(
        **kwargs
    )
    bricks.camera_code_detection = detection_mod
    bricks.image_classification = classification_mod
    arduino_pkg.app_bricks = bricks

    return fakes
