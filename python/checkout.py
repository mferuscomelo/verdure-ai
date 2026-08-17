"""Orchestrates one captured frame end to end: route to a flow, resolve the
item and its discount, mint a redeemable code. The produce side is a stub
until the Edge Impulse freshness classifier exists.
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
from pricing import PriceResult, price_packaged


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


def _produce_stub_result() -> ScanResult:
    return ScanResult(
        flow="produce",
        item_name="Unidentified produce",
        for_sale=False,
        base_price=None,
        discount_pct=None,
        final_price=None,
        discount_code=None,
        qr_data_uri=None,
        detail="Produce freshness classifier not yet available (Edge Impulse model pending)",
    )


def _price_packaged_item(image: np.ndarray) -> tuple[PriceResult, str]:
    date_result = ocr.read_best_by_date(image)
    if date_result.parsed_date is None:
        price = PriceResult(
            base_price=config.PACKAGED_DEFAULT_BASE_PRICE,
            discount_pct=0,
            final_price=config.PACKAGED_DEFAULT_BASE_PRICE,
            for_sale=True,
            tier_label="no_date_detected",
        )
        return price, "no best-by date detected; priced at full value"

    days_until_expiry = (date_result.parsed_date - date.today()).days
    price = price_packaged(config.PACKAGED_DEFAULT_BASE_PRICE, days_until_expiry)
    return price, f"best-by {date_result.parsed_date.isoformat()}"


def process_capture(
    image: np.ndarray, code_detector: CodeDetector, weight_grams: float | None = None
) -> ScanResult:
    routing = router.route_item(image, code_detector)
    if routing.flow == "produce":
        return _produce_stub_result()

    product = product_lookup.lookup_product(routing.barcode)
    item_name = product.name if product.found else f"Unknown item ({routing.barcode})"

    price, detail = _price_packaged_item(image)

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
    )
