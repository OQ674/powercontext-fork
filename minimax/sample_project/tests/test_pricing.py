"""阶梯折扣回归测试（SPEC-PRC-001）。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from order_fulfillment.pricing import discount_rate


def test_below_first_tier_has_no_discount():
    assert discount_rate(Decimal("99.99")) == Decimal("1.00")


def test_first_tier_boundary_is_inclusive():
    assert discount_rate(Decimal("100.00")) == Decimal("0.95")


def test_second_tier_boundary_is_inclusive():
    assert discount_rate(Decimal("500.00")) == Decimal("0.90")


def test_above_second_tier_keeps_the_same_rate():
    assert discount_rate(Decimal("1200.75")) == Decimal("0.90")


def test_float_input_is_rejected():
    with pytest.raises(ValueError):
        discount_rate(100.0)
