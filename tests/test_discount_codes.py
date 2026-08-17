import re

import pytest

from app import discount_codes


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    monkeypatch.setattr(discount_codes, "_active_codes", {})


def test_generate_discount_code_has_expected_format():
    result = discount_codes.generate_discount_code("Apple (1kg)", discount_pct=15, final_price=2.13)
    assert re.fullmatch(r"[A-Z0-9]{6}", result.code)


def test_generate_discount_code_returns_qr_data_uri():
    result = discount_codes.generate_discount_code("Apple (1kg)", discount_pct=15, final_price=2.13)
    assert result.qr_data_uri.startswith("data:image/png;base64,")


def test_redeem_discount_code_returns_stored_details():
    generated = discount_codes.generate_discount_code("Apple (1kg)", discount_pct=15, final_price=2.13)
    redeemed = discount_codes.redeem_discount_code(generated.code)
    assert redeemed == {"item_name": "Apple (1kg)", "discount_pct": 15, "final_price": 2.13}


def test_redeem_unknown_code_returns_none():
    assert discount_codes.redeem_discount_code("NOPE99") is None


def test_generate_discount_code_is_unique_across_calls():
    codes = {discount_codes.generate_discount_code("Item", 0, 1.0).code for _ in range(20)}
    assert len(codes) == 20
