from unittest.mock import Mock

import numpy as np

import router
from code_detector import CodeDetection, CodeDetector

ANY_FRAME = np.zeros((8, 8, 3), dtype=np.uint8)


def _detector(detection=None):
    detector = Mock(spec=CodeDetector)
    detector.get_current_detection.return_value = detection
    return detector


def test_route_item_with_a_code_goes_to_the_packaged_flow():
    detection = CodeDetection(value="070970474088", symbology="UPCA")

    result = router.route_item(ANY_FRAME, _detector(detection))

    assert result.flow == "packaged"
    assert result.barcode == "070970474088"


def test_route_item_without_a_code_goes_to_the_produce_flow():
    result = router.route_item(ANY_FRAME, _detector(None))

    assert result.flow == "produce"
    assert result.barcode is None
