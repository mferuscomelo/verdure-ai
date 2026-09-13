"""Price and discount configuration for both item flows.

Prices are in EUR. The produce figures are typical supermarket shelf prices
per kilogram; in a real deployment this table is what a store would replace
with a feed from its own POS system.
"""

PRODUCE_PRICE_PER_KG = {
    "apple": 2.49,
    "banana": 1.79,
    "tomato": 3.29,
    "orange": 2.29,
    "potato": 1.29,
}

# tier -> discount %, in "best to worst" order. `None` means the item is
# flagged not-for-sale instead of priced (matches real shrink workflows).
PRODUCE_DISCOUNT_BY_TIER = {
    "gradeA": 0,
    "gradeB": 15,
    "gradeC": 35,
    "reject": None,
}

# A prediction below this is treated as "not recognised" -- the scale asks
# for the item to be re-placed rather than pricing a low-confidence guess.
PRODUCE_MIN_CONFIDENCE = 0.6

# (days-until-expiry upper bound inclusive, discount %), ordered tightest-first.
# Anything past the last bound falls through to PACKAGED_DEFAULT_DISCOUNT_PCT.
# Negative days (already past best-by) are always a reject, regardless of table.
PACKAGED_DISCOUNT_TIERS = [
    (7, 35),
    (30, 15),
]
PACKAGED_DEFAULT_DISCOUNT_PCT = 0

# Open Food Facts identifies a product but carries no reliable price, so
# shelf prices live here. A store would source these from its POS; for the
# demo it is a small table of the products on the bench, then a per-category
# band, then a flat default.
PACKAGED_PRICE_BY_BARCODE = {
    "4001686327517": 1.99,  # gummy bears, 200 g bag
    "4316268681230": 0.99,  # chickpeas, 400 g can
    "070970474088": 1.49,  # boxed candy
}

# Matched against the Open Food Facts category string, first hit wins, so
# the more specific entries are listed before the broader ones.
PACKAGED_PRICE_BY_CATEGORY = [
    ("baby food", 2.79),
    ("cheese", 3.49),
    ("chocolate", 2.49),
    ("confectioner", 1.99),
    ("snack", 1.99),
    ("cereal", 2.99),
    ("coffee", 4.99),
    ("tea", 3.29),
    ("legume", 0.99),
    ("canned", 1.29),
    ("pasta", 1.49),
    ("sauce", 1.79),
    ("dairy", 1.59),
    ("beverage", 1.29),
    ("frozen", 2.99),
]

PACKAGED_DEFAULT_BASE_PRICE = 2.49
