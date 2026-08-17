from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import cv2
import pytest

import checkout
import discount_codes
import ocr
import product_lookup
import router
from code_detector import SimulatedCodeDetector

# No fixture image contains both a barcode and a printed date (they're
# separate purpose-built sets), so packaged-flow tests mock routing/OCR to
# control which branch runs while keeping pricing/discount-code generation
# real. Using a fixed offset from date.today() (not a fixture's baked-in
# date) keeps tier assertions stable regardless of when the suite runs.
NO_BARCODE_FIXTURE = Path(__file__).parent / "fixtures" / "best_by_dates" / "clean_iso.png"
ANY_IMAGE = cv2.imread(str(NO_BARCODE_FIXTURE))

SAMPLE_PRODUCT = product_lookup.ProductInfo(
    barcode="070970474088", found=True, name="Mike and Ike", brand="Just Born",
    image_url=None, source="network",
)


@pytest.fixture(autouse=True)
def isolated_discount_registry(monkeypatch):
    monkeypatch.setattr(discount_codes, "_active_codes", {})


def test_process_capture_produce_flow_returns_stub_result():
    result = checkout.process_capture(ANY_IMAGE, SimulatedCodeDetector(), weight_grams=180)

    assert result.flow == "produce"
    assert not result.for_sale
    assert result.discount_code is None


@patch("checkout.ocr.read_best_by_date")
@patch("checkout.product_lookup.lookup_product")
@patch("checkout.router.route_item")
def test_process_capture_packaged_flow_applies_urgent_discount(mock_route, mock_lookup, mock_ocr):
    mock_route.return_value = router.RoutingResult(flow="packaged", barcode="070970474088")
    mock_lookup.return_value = SAMPLE_PRODUCT
    mock_ocr.return_value = ocr.DateExtractionResult(
        raw_text="", parsed_date=date.today() + timedelta(days=5), matched_substring="",
    )

    result = checkout.process_capture(ANY_IMAGE, SimulatedCodeDetector())

    assert result.flow == "packaged"
    assert result.item_name == "Mike and Ike"
    assert result.for_sale
    assert result.discount_pct == 35
    assert result.final_price == round(result.base_price * 0.65, 2)
    assert result.discount_code is not None

    redeemed = discount_codes.redeem_discount_code(result.discount_code)
    assert redeemed["final_price"] == result.final_price


@patch("checkout.ocr.read_best_by_date")
@patch("checkout.product_lookup.lookup_product")
@patch("checkout.router.route_item")
def test_process_capture_packaged_flow_no_date_prices_at_full_value(mock_route, mock_lookup, mock_ocr):
    mock_route.return_value = router.RoutingResult(flow="packaged", barcode="070970474088")
    mock_lookup.return_value = SAMPLE_PRODUCT
    mock_ocr.return_value = ocr.DateExtractionResult(raw_text="", parsed_date=None, matched_substring=None)

    result = checkout.process_capture(ANY_IMAGE, SimulatedCodeDetector())

    assert result.for_sale
    assert result.discount_pct == 0
    assert result.final_price == result.base_price
    assert result.discount_code is not None


@patch("checkout.ocr.read_best_by_date")
@patch("checkout.product_lookup.lookup_product")
@patch("checkout.router.route_item")
def test_process_capture_packaged_flow_expired_is_not_for_sale(mock_route, mock_lookup, mock_ocr):
    mock_route.return_value = router.RoutingResult(flow="packaged", barcode="070970474088")
    mock_lookup.return_value = SAMPLE_PRODUCT
    mock_ocr.return_value = ocr.DateExtractionResult(
        raw_text="", parsed_date=date.today() - timedelta(days=2), matched_substring="",
    )

    result = checkout.process_capture(ANY_IMAGE, SimulatedCodeDetector())

    assert not result.for_sale
    assert result.final_price is None
    assert result.discount_code is None
