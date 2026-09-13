"""The detector bridges two different clocks: the brick reads codes
continuously off the live feed, while the checkout asks its question once,
at the moment the weight settles. These cover what it remembers in between.
"""
import types
from unittest.mock import Mock

import pytest

import code_detector


class _FakeBrick:
    """Stands in for CameraCodeDetection, capturing the registered callback
    so a test can fire a detection the way the live feed would."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.callback = None
        self.started = False

    def on_detect(self, callback):
        self.callback = callback

    def start(self):
        self.started = True

    def detect(self, value, symbology="EAN13"):
        self.callback(None, types.SimpleNamespace(content=value, type=symbology))


@pytest.fixture
def brick(arduino):
    created = _FakeBrick()
    arduino.code_detection_cls = lambda **kwargs: _configure(created, kwargs)
    return created


def _configure(brick, kwargs):
    brick.kwargs = kwargs
    return brick


def test_nothing_detected_yet_reads_as_no_code(brick):
    detector = code_detector.get_code_detector()

    assert detector.get_current_detection() is None


def test_a_code_seen_on_the_feed_is_reported_at_scan_time(brick):
    detector = code_detector.get_code_detector()

    brick.detect("4001686327517")

    detection = detector.get_current_detection()
    assert detection.value == "4001686327517"
    assert detection.symbology == "EAN13"


def test_the_code_survives_until_the_item_leaves_the_scale(brick):
    detector = code_detector.get_code_detector()
    brick.detect("4001686327517")

    # Several polls happen between the code being read and the weight settling.
    assert detector.get_current_detection() is not None
    assert detector.get_current_detection() is not None


def test_resetting_forgets_the_previous_item(brick):
    detector = code_detector.get_code_detector()
    brick.detect("4001686327517")

    detector.on_item_reset()

    assert detector.get_current_detection() is None


def test_the_latest_code_wins_within_one_item(brick):
    detector = code_detector.get_code_detector()

    brick.detect("4001686327517")
    brick.detect("4316268681230")

    assert detector.get_current_detection().value == "4316268681230"


def test_start_starts_the_brick(brick):
    code_detector.get_code_detector().start()

    assert brick.started


def test_the_shared_camera_is_handed_to_the_brick(brick):
    sentinel = Mock()

    code_detector.get_code_detector(camera=sentinel)

    assert brick.kwargs["camera"] is sentinel
