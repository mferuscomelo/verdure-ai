from pathlib import Path

import cv2

from app import router

BARCODE_FIXTURE = Path(__file__).parent / "fixtures" / "barcodes" / "rot_000.png"
NO_BARCODE_FIXTURE = Path(__file__).parent / "fixtures" / "best_by_dates" / "clean_iso.png"


def test_route_item_with_barcode_goes_to_packaged_flow():
    image = cv2.imread(str(BARCODE_FIXTURE))
    result = router.route_item(image)
    assert result.flow == "packaged"
    assert result.barcode == "070970474088"


def test_route_item_without_barcode_goes_to_produce_flow():
    image = cv2.imread(str(NO_BARCODE_FIXTURE))
    result = router.route_item(image)
    assert result.flow == "produce"
    assert result.barcode is None
