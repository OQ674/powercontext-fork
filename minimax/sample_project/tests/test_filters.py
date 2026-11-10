"""订单筛选的既有行为回归测试（SPEC-ORD-001 / SPEC-ORD-002）。

这些用例在功能修改前后都必须通过，用于证明新增筛选条件没有破坏原有行为。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from order_fulfillment.filters import filter_orders
from order_fulfillment.models import Order, OrderStatus


def make_orders() -> list[Order]:
    return [
        Order("O-2", "C-1", OrderStatus.PENDING, Decimal("20.00"), "2026-01-02"),
        Order("O-1", "C-1", OrderStatus.SHIPPED, Decimal("10.00"), "2026-01-01"),
        Order("O-3", "C-2", OrderStatus.SHIPPED, Decimal("30.00"), "2026-01-03"),
    ]


def test_returns_all_orders_by_default():
    result = filter_orders(make_orders())
    assert [order.order_id for order in result] == ["O-1", "O-2", "O-3"]


def test_filters_by_status_instance():
    result = filter_orders(make_orders(), status=OrderStatus.SHIPPED)
    assert [order.order_id for order in result] == ["O-1", "O-3"]


def test_filters_by_status_string():
    result = filter_orders(make_orders(), status="pending")
    assert [order.order_id for order in result] == ["O-2"]


def test_invalid_status_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        filter_orders(make_orders(), status="not-a-status")
    assert "not-a-status" in str(excinfo.value)


def test_sort_by_created_at_is_the_default():
    orders = [
        Order("O-2", "C-1", OrderStatus.PENDING, Decimal("1.00"), "2026-02-01"),
        Order("O-1", "C-1", OrderStatus.PENDING, Decimal("1.00"), "2026-01-01"),
    ]
    assert [order.order_id for order in filter_orders(orders)] == ["O-1", "O-2"]


def test_sort_by_amount_uses_exact_decimal_order():
    orders = [
        Order("O-1", "C-1", OrderStatus.PENDING, Decimal("9.10"), "2026-01-01"),
        Order("O-2", "C-1", OrderStatus.PENDING, Decimal("9.20"), "2026-01-02"),
        Order("O-3", "C-1", OrderStatus.PENDING, Decimal("9.30"), "2026-01-03"),
    ]
    assert [order.order_id for order in filter_orders(orders, sort_by="amount")] == ["O-1", "O-2", "O-3"]


def test_unknown_sort_by_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        filter_orders(make_orders(), sort_by="customer")
    assert "customer" in str(excinfo.value)


def test_limit_and_offset_paginate():
    result = filter_orders(make_orders(), offset=1, limit=1)
    assert [order.order_id for order in result] == ["O-2"]


def test_non_positive_limit_raises_value_error():
    with pytest.raises(ValueError):
        filter_orders(make_orders(), limit=0)


def test_input_is_not_mutated():
    orders = make_orders()
    filter_orders(orders, status=OrderStatus.SHIPPED)
    assert [order.order_id for order in orders] == ["O-2", "O-1", "O-3"]
