"""Open Food Facts product lookup with an indefinite local JSON cache.

Looks up a decoded barcode against the Open Food Facts API and caches the
result locally (flat JSON, keyed by barcode) so repeat/offline scans don't
need a network call. No TTL by design: product identity/branding data
changes rarely, and offline demo reliability matters more than freshness.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import requests

OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
CACHE_PATH = Path(__file__).parent / "data" / "product_cache.json"
REQUEST_TIMEOUT_S = 5
# Open Food Facts rejects requests with a generic/default User-Agent (returns
# 403); their API usage policy requires an app-identifying one.
REQUEST_HEADERS = {"User-Agent": "VerdureAI/1.0 (checkout-scale-demo; +https://github.com/)"}


@dataclass
class ProductInfo:
    barcode: str
    found: bool
    name: str | None
    brand: str | None
    image_url: str | None
    source: str  # "cache" | "network" | "network_error"
    category: str | None = None


def _normalize_barcode(barcode: str) -> str:
    return "".join(ch for ch in barcode if ch.isdigit())


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}  # corrupt cache shouldn't crash a demo; treat as empty


def _write_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CACHE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(cache, indent=2))
    tmp_path.replace(CACHE_PATH)  # atomic swap, avoids a half-written cache file


def _parse_off_response(payload: dict) -> dict:
    if payload.get("status") != 1:
        return {"found": False, "name": None, "brand": None, "image_url": None, "category": None}
    product = payload.get("product", {})
    brands = product.get("brands")
    return {
        "found": True,
        "name": product.get("product_name") or None,
        "brand": brands.split(",")[0].strip() if brands else None,
        "image_url": product.get("image_front_url") or product.get("image_url") or None,
        # Comma-separated tag path, broadest first -- pricing matches keywords against it.
        "category": product.get("categories") or None,
    }


def lookup_product(barcode: str, *, use_cache: bool = True) -> ProductInfo:
    barcode = _normalize_barcode(barcode)
    cache = _load_cache() if use_cache else {}

    if barcode in cache:
        return ProductInfo(barcode=barcode, source="cache", **cache[barcode])

    try:
        resp = requests.get(
            OFF_API_URL.format(barcode=barcode), timeout=REQUEST_TIMEOUT_S, headers=REQUEST_HEADERS
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException:
        # Transient failure: do NOT cache, so the next scan retries the network.
        return ProductInfo(barcode=barcode, found=False, name=None, brand=None,
                            image_url=None, source="network_error")

    fields = _parse_off_response(payload)
    # Cache both "found" and definitive "not found" answers -- both are real
    # OFF answers and caching them is what makes repeat/offline scans work.
    cache[barcode] = fields
    _write_cache(cache)
    return ProductInfo(barcode=barcode, source="network", **fields)
