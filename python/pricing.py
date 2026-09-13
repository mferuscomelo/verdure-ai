"""Flow-agnostic pricing: base price + discount tier -> final price.

Produce and packaged-goods flows each resolve their own discount tier from
`config.py`, then both funnel through the same `apply_discount`.
"""
from dataclasses import dataclass

from config import (
    PACKAGED_DEFAULT_BASE_PRICE,
    PACKAGED_DEFAULT_DISCOUNT_PCT,
    PACKAGED_DISCOUNT_TIERS,
    PACKAGED_PRICE_BY_BARCODE,
    PACKAGED_PRICE_BY_CATEGORY,
    PRODUCE_DISCOUNT_BY_TIER,
    PRODUCE_PRICE_PER_KG,
)


@dataclass
class PriceResult:
    base_price: float
    discount_pct: float
    final_price: float | None  # None when for_sale is False
    for_sale: bool
    tier_label: str


def apply_discount(base_price: float, discount_pct: float) -> float:
    return round(base_price * (1 - discount_pct / 100), 2)


def price_produce(produce_type: str, tier: str, weight_kg: float) -> PriceResult:
    price_per_kg = PRODUCE_PRICE_PER_KG[produce_type]
    discount_pct = PRODUCE_DISCOUNT_BY_TIER[tier]
    base_price = round(price_per_kg * weight_kg, 2)

    if discount_pct is None:
        return PriceResult(base_price, discount_pct=0, final_price=None, for_sale=False, tier_label=tier)

    return PriceResult(
        base_price,
        discount_pct=discount_pct,
        final_price=apply_discount(base_price, discount_pct),
        for_sale=True,
        tier_label=tier,
    )


def packaged_base_price(barcode: str | None, category: str | None = None) -> float:
    """Shelf price for a packaged item: exact product, then category, then default."""
    if barcode is not None and barcode in PACKAGED_PRICE_BY_BARCODE:
        return PACKAGED_PRICE_BY_BARCODE[barcode]

    if category:
        haystack = category.lower()
        for keyword, price in PACKAGED_PRICE_BY_CATEGORY:
            if keyword in haystack:
                return price

    return PACKAGED_DEFAULT_BASE_PRICE


def price_packaged(base_price: float, days_until_expiry: int) -> PriceResult:
    if days_until_expiry < 0:
        return PriceResult(base_price, discount_pct=0, final_price=None, for_sale=False, tier_label="expired")

    discount_pct = PACKAGED_DEFAULT_DISCOUNT_PCT
    for max_days, tier_pct in PACKAGED_DISCOUNT_TIERS:
        if days_until_expiry <= max_days:
            discount_pct = tier_pct
            break

    return PriceResult(
        base_price,
        discount_pct=discount_pct,
        final_price=apply_discount(base_price, discount_pct),
        for_sale=True,
        tier_label=f"{discount_pct}pct",
    )
