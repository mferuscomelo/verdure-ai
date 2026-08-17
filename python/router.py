"""Routes a captured frame to the packaged-goods or produce flow based on
barcode presence -- mirrors real self-checkout behavior since produce
rarely carries a machine-readable barcode, while packaged goods do.
"""
from dataclasses import dataclass

import numpy as np

from code_detector import CodeDetector


@dataclass
class RoutingResult:
    flow: str  # "packaged" | "produce"
    barcode: str | None


def route_item(image: np.ndarray, code_detector: CodeDetector) -> RoutingResult:
    barcode = code_detector.get_current_detection(image)
    if barcode is not None:
        return RoutingResult(flow="packaged", barcode=barcode.value)
    return RoutingResult(flow="produce", barcode=None)
