import json
from unittest.mock import Mock, patch

import pytest

import product_lookup

SAMPLE_BARCODE = "070970474088"
SAMPLE_OFF_RESPONSE = {
    "status": 1,
    "product": {
        "product_name": "Mike and Ike",
        "brands": "Just Born,Mike and Ike",
        "image_front_url": "https://images.openfoodfacts.org/example/front.jpg",
    },
}


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "product_cache.json"
    monkeypatch.setattr(product_lookup, "CACHE_PATH", cache_path)
    return cache_path


def _mock_response(json_body):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json.return_value = json_body
    return resp


@patch("product_lookup.requests.get")
def test_lookup_cache_miss_then_hit(mock_get, isolated_cache):
    mock_get.return_value = _mock_response(SAMPLE_OFF_RESPONSE)

    first = product_lookup.lookup_product(SAMPLE_BARCODE)
    assert first.found and first.source == "network" and first.name == "Mike and Ike"
    mock_get.assert_called_once()

    second = product_lookup.lookup_product(SAMPLE_BARCODE)
    assert second.source == "cache" and second.name == "Mike and Ike"
    mock_get.assert_called_once()  # not called again -- confirms cache hit

    assert SAMPLE_BARCODE in json.loads(isolated_cache.read_text())


@patch("product_lookup.requests.get")
def test_lookup_not_found_is_cached(mock_get, isolated_cache):
    mock_get.return_value = _mock_response({"status": 0})

    result = product_lookup.lookup_product(SAMPLE_BARCODE)
    assert not result.found and result.source == "network"

    result2 = product_lookup.lookup_product(SAMPLE_BARCODE)
    assert result2.source == "cache"
    mock_get.assert_called_once()


@patch("product_lookup.requests.get")
def test_lookup_network_error_not_cached(mock_get, isolated_cache):
    mock_get.side_effect = product_lookup.requests.RequestException("boom")

    result = product_lookup.lookup_product(SAMPLE_BARCODE)
    assert not result.found and result.source == "network_error"
    assert not isolated_cache.exists()  # transient failure must not be cached
