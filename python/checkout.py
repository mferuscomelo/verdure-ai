"""Orchestrates one captured frame end to end: route to a flow, resolve the
item and its discount, mint a redeemable code.

Produce is priced from its weight and the condition grade the classifier
returns; packaged goods from a shelf price and how close the printed
best-by date is. Both funnel into the same discount and QR-code step, so
the checkout screen renders them identically.
"""
from dataclasses import dataclass
from datetime import date

import numpy as np

import config
import discount_codes
import ocr
import product_lookup
import router
from code_detector import CodeDetector
from pricing import PriceResult, packaged_base_price, price_packaged, price_produce
from produce_classifier import ProduceClassifier

TIER_LABELS = {
    "gradeA": "Grade A",
    "gradeB": "Grade B",
    "gradeC": "Grade C",
    "reject": "Not fit for sale",
}


@dataclass
class ScanResult:
    flow: str  # "packaged" | "produce"
    item_name: str
    for_sale: bool
    base_price: float | None
    discount_pct: float | None
    final_price: float | None
    discount_code: str | None
    qr_data_uri: str | None
    detail: str
    weight_grams: float | None = None
    produce_type: str | None = None
    grade: str | None = None
    price_per_kg: float | None = None


def _unpriced(flow: str, item_name: str, detail: str, **extra) -> ScanResult:
    return ScanResult(
        flow=flow,
        item_name=item_name,
        for_sale=False,
        base_price=None,
        discount_pct=None,
        final_price=None,
        discount_code=None,
        qr_data_uri=None,
        detail=detail,
        **extra,
    )


def _price_packaged_item(image: np.ndarray, base_price: float) -> tuple[PriceResult, str]:
    date_result = ocr.read_best_by_date(image)
    if date_result.parsed_date is None:
        price = PriceResult(
            base_price=base_price,
            discount_pct=0,
            final_price=base_price,
            for_sale=True,
            tier_label="no_date_detected",
        )
        return price, "no best-by date detected; priced at full value"

    days_until_expiry = (date_result.parsed_date - date.today()).days
    price = price_packaged(base_price, days_until_expiry)
    return price, f"best-by {date_result.parsed_date.isoformat()}"


def _process_produce(
    image: np.ndarray, produce_classifier: ProduceClassifier, weight_grams: float | None
) -> ScanResult:
    graded = produce_classifier.classify(image)
    if graded is None:
        return _unpriced(
            "produce",
            "Item not recognised",
            "Please place a single item squarely on the scale",
            weight_grams=weight_grams,
        )

    item_name = graded.produce_type.replace("_", " ").title()
    tier_label = TIER_LABELS.get(graded.tier, graded.tier)
    common = {
        "weight_grams": weight_grams,
        "produce_type": graded.produce_type,
        "grade": graded.tier,
        "price_per_kg": config.PRODUCE_PRICE_PER_KG[graded.produce_type],
    }

    if not weight_grams:
        return _unpriced("produce", item_name, "Waiting for a stable weight", **common)

    price = price_produce(graded.produce_type, graded.tier, weight_grams / 1000)

    if not price.for_sale:
        return _unpriced(
            "produce", item_name, f"{tier_label} -- pulled from sale", **common
        )

    code = discount_codes.generate_discount_code(item_name, price.discount_pct, price.final_price)
    return ScanResult(
        flow="produce",
        item_name=item_name,
        for_sale=True,
        base_price=price.base_price,
        discount_pct=price.discount_pct,
        final_price=price.final_price,
        discount_code=code.code,
        qr_data_uri=code.qr_data_uri,
        detail=f"{tier_label} ({graded.confidence:.0%} confidence)",
        **common,
    )


def _process_packaged(
    image: np.ndarray, barcode: str, weight_grams: float | None
) -> ScanResult:
    product = product_lookup.lookup_product(barcode)
    item_name = product.name if product.found else f"Unknown item ({barcode})"
    base_price = packaged_base_price(barcode, product.category)

    price, detail = _price_packaged_item(image, base_price)

    if not price.for_sale:
        return ScanResult(
            flow="packaged",
            item_name=item_name,
            for_sale=False,
            base_price=price.base_price,
            discount_pct=None,
            final_price=None,
            discount_code=None,
            qr_data_uri=None,
            detail=f"{detail} -- expired, not for sale",
            weight_grams=weight_grams,
        )

    code = discount_codes.generate_discount_code(item_name, price.discount_pct, price.final_price)
    return ScanResult(
        flow="packaged",
        item_name=item_name,
        for_sale=True,
        base_price=price.base_price,
        discount_pct=price.discount_pct,
        final_price=price.final_price,
        discount_code=code.code,
        qr_data_uri=code.qr_data_uri,
        detail=detail,
        weight_grams=weight_grams,
    )


def process_capture(
    image: np.ndarray,
    code_detector: CodeDetector,
    produce_classifier: ProduceClassifier,
    weight_grams: float | None = None,
) -> ScanResult:
    routing = router.route_item(image, code_detector)
    if routing.flow == "produce":
        return _process_produce(image, produce_classifier, weight_grams)
    return _process_packaged(image, routing.barcode, weight_grams)
