from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import pytest

import checkout
import config
import discount_codes
import ocr
import product_lookup
import router
from code_detector import CodeDetection, CodeDetector
from produce_classifier import ProduceClassifier, ProduceGrade

# The checkout takes its frame from the camera and its verdicts from the two
# vision pipelines, so these tests drive those boundaries with doubles and
# let the routing, pricing and discount-code logic run for real. Expiry
# tiers use an offset from date.today() rather than a fixture's baked-in
# date, so the assertions don't drift as real time passes.
ANY_IMAGE = cv2.imread(
    str(Path(__file__).parent / "fixtures" / "best_by_dates" / "clean_iso.png")
)

PACKAGED_BARCODE = "070970474088"
SAMPLE_PRODUCT = product_lookup.ProductInfo(
    barcode=PACKAGED_BARCODE, found=True, name="Mike and Ike", brand="Just Born",
    image_url=None, source="network", category="Snacks, Sweets, Confectioneries",
)


@pytest.fixture(autouse=True)
def isolated_discount_registry(monkeypatch):
    monkeypatch.setattr(discount_codes, "_active_codes", {})


def _detector(detection=None):
    detector = Mock(spec=CodeDetector)
    detector.get_current_detection.return_value = detection
    return detector


def _classifier(grade=None):
    classifier = Mock(spec=ProduceClassifier)
    classifier.classify.return_value = grade
    return classifier


def _graded(produce_type="apple", tier="gradeA", confidence=0.92):
    return ProduceGrade(
        produce_type=produce_type, tier=tier, confidence=confidence,
        label=f"{produce_type}_{tier}",
    )


# --- produce flow ---------------------------------------------------------

def test_produce_top_grade_is_priced_by_weight_at_full_value():
    result = checkout.process_capture(
        ANY_IMAGE, _detector(), _classifier(_graded(tier="gradeA")), weight_grams=180
    )

    assert result.flow == "produce"
    assert result.item_name == "Apple"
    assert result.for_sale
    assert result.weight_grams == 180
    assert result.price_per_kg == config.PRODUCE_PRICE_PER_KG["apple"]
    assert result.base_price == round(config.PRODUCE_PRICE_PER_KG["apple"] * 0.180, 2)
    assert result.discount_pct == 0
    assert result.final_price == result.base_price


def test_produce_lower_grade_is_discounted_and_gets_a_redeemable_code():
    result = checkout.process_capture(
        ANY_IMAGE, _detector(), _classifier(_graded(tier="gradeC")), weight_grams=180
    )

    assert result.for_sale
    assert result.grade == "gradeC"
    assert result.discount_pct == config.PRODUCE_DISCOUNT_BY_TIER["gradeC"]
    assert result.final_price == round(result.base_price * 0.65, 2)
    assert result.qr_data_uri.startswith("data:image/png;base64,")

    redeemed = discount_codes.redeem_discount_code(result.discount_code)
    assert redeemed["final_price"] == result.final_price


def test_produce_reject_grade_is_pulled_from_sale():
    result = checkout.process_capture(
        ANY_IMAGE, _detector(), _classifier(_graded(tier="reject")), weight_grams=180
    )

    assert not result.for_sale
    assert result.final_price is None
    assert result.discount_code is None
    assert result.grade == "reject"


def test_produce_below_confidence_asks_for_the_item_to_be_replaced():
    result = checkout.process_capture(
        ANY_IMAGE, _detector(), _classifier(None), weight_grams=180
    )

    assert result.flow == "produce"
    assert not result.for_sale
    assert result.discount_code is None
    assert "re-place" in result.detail or "place" in result.detail


def test_produce_without_a_weight_is_not_priced():
    result = checkout.process_capture(
        ANY_IMAGE, _detector(), _classifier(_graded()), weight_grams=None
    )

    assert not result.for_sale
    assert result.final_price is None
    assert result.produce_type == "apple"


def test_produce_classifier_is_not_consulted_for_a_barcoded_item():
    classifier = _classifier(_graded())
    detection = CodeDetection(value=PACKAGED_BARCODE, symbology="UPCA")

    with patch("checkout.product_lookup.lookup_product", return_value=SAMPLE_PRODUCT), \
         patch("checkout.ocr.read_best_by_date") as mock_ocr:
        mock_ocr.return_value = ocr.DateExtractionResult(
            raw_text="", parsed_date=None, matched_substring=None
        )
        result = checkout.process_capture(ANY_IMAGE, _detector(detection), classifier)

    assert result.flow == "packaged"
    classifier.classify.assert_not_called()


# --- packaged flow --------------------------------------------------------

@patch("checkout.ocr.read_best_by_date")
@patch("checkout.product_lookup.lookup_product")
@patch("checkout.router.route_item")
def test_packaged_near_expiry_gets_the_urgent_discount(mock_route, mock_lookup, mock_ocr):
    mock_route.return_value = router.RoutingResult(flow="packaged", barcode=PACKAGED_BARCODE)
    mock_lookup.return_value = SAMPLE_PRODUCT
    mock_ocr.return_value = ocr.DateExtractionResult(
        raw_text="", parsed_date=date.today() + timedelta(days=5), matched_substring="",
    )

    result = checkout.process_capture(ANY_IMAGE, _detector(), _classifier())

    assert result.flow == "packaged"
    assert result.item_name == "Mike and Ike"
    assert result.for_sale
    assert result.base_price == config.PACKAGED_PRICE_BY_BARCODE[PACKAGED_BARCODE]
    assert result.discount_pct == 35
    assert result.final_price == round(result.base_price * 0.65, 2)

    redeemed = discount_codes.redeem_discount_code(result.discount_code)
    assert redeemed["final_price"] == result.final_price


@patch("checkout.ocr.read_best_by_date")
@patch("checkout.product_lookup.lookup_product")
@patch("checkout.router.route_item")
def test_packaged_without_a_readable_date_prices_at_full_value(mock_route, mock_lookup, mock_ocr):
    mock_route.return_value = router.RoutingResult(flow="packaged", barcode=PACKAGED_BARCODE)
    mock_lookup.return_value = SAMPLE_PRODUCT
    mock_ocr.return_value = ocr.DateExtractionResult(
        raw_text="", parsed_date=None, matched_substring=None
    )

    result = checkout.process_capture(ANY_IMAGE, _detector(), _classifier())

    assert result.for_sale
    assert result.discount_pct == 0
    assert result.final_price == result.base_price


@patch("checkout.ocr.read_best_by_date")
@patch("checkout.product_lookup.lookup_product")
@patch("checkout.router.route_item")
def test_packaged_past_its_best_by_is_not_for_sale(mock_route, mock_lookup, mock_ocr):
    mock_route.return_value = router.RoutingResult(flow="packaged", barcode=PACKAGED_BARCODE)
    mock_lookup.return_value = SAMPLE_PRODUCT
    mock_ocr.return_value = ocr.DateExtractionResult(
        raw_text="", parsed_date=date.today() - timedelta(days=2), matched_substring="",
    )

    result = checkout.process_capture(ANY_IMAGE, _detector(), _classifier())

    assert not result.for_sale
    assert result.final_price is None
    assert result.discount_code is None


@patch("checkout.ocr.read_best_by_date")
@patch("checkout.product_lookup.lookup_product")
@patch("checkout.router.route_item")
def test_packaged_unknown_barcode_falls_back_to_category_price(mock_route, mock_lookup, mock_ocr):
    mock_route.return_value = router.RoutingResult(flow="packaged", barcode="9999999999999")
    mock_lookup.return_value = product_lookup.ProductInfo(
        barcode="9999999999999", found=True, name="Some Cheese", brand=None,
        image_url=None, source="network", category="Dairies, Cheeses",
    )
    mock_ocr.return_value = ocr.DateExtractionResult(
        raw_text="", parsed_date=None, matched_substring=None
    )

    result = checkout.process_capture(ANY_IMAGE, _detector(), _classifier())

    assert result.base_price == dict(config.PACKAGED_PRICE_BY_CATEGORY)["cheese"]
