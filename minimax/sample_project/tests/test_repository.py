"""订单仓储回归测试。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from order_fulfillment.models import OrderStatus
from order_fulfillment.repository import InMemoryOrderRepository, load_orders_from_csv

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "orders.csv"


def test_loads_every_row_from_the_csv_file():
    orders = load_orders_from_csv(DATA_FILE)
    assert len(orders) == 8


def test_amount_is_parsed_as_decimal():
    orders = load_orders_from_csv(DATA_FILE)
    assert all(isinstance(order.amount, Decimal) for order in orders)
    assert orders[0].amount == Decimal("99.99")


def test_status_is_parsed_into_the_enum():
    orders = load_orders_from_csv(DATA_FILE)
    assert orders[0].status is OrderStatus.PENDING
    assert orders[1].status is OrderStatus.SHIPPED


def test_repository_returns_a_copy():
    repository = InMemoryOrderRepository(load_orders_from_csv(DATA_FILE))
    first = repository.all()
    first.clear()
    assert len(repository.all()) == 8


def test_unknown_status_in_csv_raises_value_error(tmp_path):
    broken = tmp_path / "broken.csv"
    broken.write_text(
        "order_id,customer_id,status,amount,created_at\nO-1,C-1,unknown,1.00,2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_orders_from_csv(broken)
