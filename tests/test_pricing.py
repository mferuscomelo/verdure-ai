import pytest

from app import pricing


def test_apply_discount_no_discount_returns_base_price():
    assert pricing.apply_discount(10.00, 0) == 10.00


def test_apply_discount_reduces_by_percentage():
    assert pricing.apply_discount(10.00, 25) == 7.50


def test_apply_discount_rounds_to_cents():
    assert pricing.apply_discount(9.99, 15) == 8.49  # 8.4915 -> 8.49


def test_price_produce_grade_a_no_discount():
    result = pricing.price_produce("apple", "gradeA", weight_kg=2.0)
    assert result.for_sale
    assert result.base_price == 5.00
    assert result.discount_pct == 0
    assert result.final_price == 5.00


def test_price_produce_grade_b_applies_discount():
    result = pricing.price_produce("banana", "gradeB", weight_kg=1.0)
    assert result.for_sale
    assert result.base_price == 1.20
    assert result.discount_pct == 15
    assert result.final_price == 1.02


def test_price_produce_reject_tier_not_for_sale():
    result = pricing.price_produce("tomato", "reject", weight_kg=1.0)
    assert not result.for_sale
    assert result.final_price is None


def test_price_produce_unknown_type_raises():
    with pytest.raises(KeyError):
        pricing.price_produce("durian", "gradeA", weight_kg=1.0)


def test_price_packaged_far_from_expiry_no_discount():
    result = pricing.price_packaged(4.00, days_until_expiry=45)
    assert result.for_sale
    assert result.discount_pct == 0
    assert result.final_price == 4.00


def test_price_packaged_within_medium_window():
    result = pricing.price_packaged(4.00, days_until_expiry=30)
    assert result.for_sale
    assert result.discount_pct == 15
    assert result.final_price == 3.40


def test_price_packaged_within_urgent_window():
    result = pricing.price_packaged(4.00, days_until_expiry=7)
    assert result.for_sale
    assert result.discount_pct == 35
    assert result.final_price == 2.60


def test_price_packaged_expired_not_for_sale():
    result = pricing.price_packaged(4.00, days_until_expiry=-1)
    assert not result.for_sale
    assert result.final_price is None
