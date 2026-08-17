"""Static price/discount configuration for both item flows.

Placeholder values for the hackathon demo, not researched retail pricing.
"""

PRODUCE_PRICE_PER_KG = {
    "apple": 2.50,
    "banana": 1.20,
    "tomato": 3.00,
    "orange": 2.20,
    "potato": 1.50,
}

# tier -> discount %, in "best to worst" order. `None` means the item is
# flagged not-for-sale instead of priced (matches real shrink workflows).
PRODUCE_DISCOUNT_BY_TIER = {
    "gradeA": 0,
    "gradeB": 15,
    "gradeC": 35,
    "reject": None,
}

# (days-until-expiry upper bound inclusive, discount %), ordered tightest-first.
# Anything past the last bound falls through to PACKAGED_DEFAULT_DISCOUNT_PCT.
# Negative days (already past best-by) are always a reject, regardless of table.
PACKAGED_DISCOUNT_TIERS = [
    (7, 35),
    (30, 15),
]
PACKAGED_DEFAULT_DISCOUNT_PCT = 0

# Open Food Facts doesn't reliably carry price data -- flat placeholder base
# price for the packaged-goods flow until a real POS price source exists.
PACKAGED_DEFAULT_BASE_PRICE = 3.00
