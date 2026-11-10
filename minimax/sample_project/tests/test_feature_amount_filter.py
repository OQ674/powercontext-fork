"""目标功能测试：订单金额区间筛选（SPEC-ORD-003）。

本文件是本次任务的**目标功能测试**。修改前必须因目标行为尚未实现而失败，
修改后必须全部通过；测试集在修改前后保持一致，不允许删除断言或修改预期值。

覆盖 SPEC-ORD-003 的 7 条验收标准。
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

import pytest

from order_fulfillment.filters import filter_orders
from order_fulfillment.models import Order, OrderStatus
from order_fulfillment.repository import InMemoryOrderRepository, load_orders_from_csv
from order_fulfillment.service import create_server

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "orders.csv"


@pytest.fixture()
def orders() -> list[Order]:
    return load_orders_from_csv(DATA_FILE)


def test_no_amount_filter_returns_every_order(orders):
    """验收标准 1：不传金额条件时行为与既有版本一致。"""

    result = filter_orders(orders)
    assert len(result) == len(orders)


def test_min_amount_keeps_orders_on_or_above_the_boundary(orders):
    """验收标准 2、7：只传 min_amount 时保留 amount >= min_amount 的订单。"""

    result = filter_orders(orders, min_amount=Decimal("199.50"))
    assert [order.order_id for order in result] == ["O-1003", "O-1004", "O-1006", "O-1007"]


def test_max_amount_keeps_orders_on_or_below_the_boundary(orders):
    """验收标准 2、7：只传 max_amount 时保留 amount <= max_amount 的订单。"""

    result = filter_orders(orders, max_amount=Decimal("100.00"))
    assert [order.order_id for order in result] == ["O-1001", "O-1002", "O-1005", "O-1008"]


def test_amount_range_is_inclusive_on_both_ends(orders):
    """验收标准 3：同时传入时为闭区间，两端订单都要保留。"""

    result = filter_orders(orders, min_amount=Decimal("100.00"), max_amount=Decimal("249.99"))
    assert [order.order_id for order in result] == ["O-1002", "O-1003", "O-1006"]


def test_min_amount_greater_than_max_amount_is_rejected(orders):
    """验收标准 4：区间颠倒必须抛出 ValueError，错误信息包含两个参数名。"""

    with pytest.raises(ValueError) as excinfo:
        filter_orders(orders, min_amount=Decimal("500.00"), max_amount=Decimal("100.00"))
    message = str(excinfo.value)
    assert "min_amount" in message
    assert "max_amount" in message


@pytest.mark.parametrize("bad_value", ["100.00", 1.5, object()])
def test_non_numeric_amount_is_rejected(orders, bad_value):
    """验收标准 5：非 Decimal/整数的金额取值必须抛出 ValueError。"""

    with pytest.raises(ValueError):
        filter_orders(orders, min_amount=bad_value)


def test_amount_comparison_uses_exact_decimal_arithmetic():
    """验收标准 6：使用 Decimal 精确比较，0.1 + 0.2 类误差不得影响边界判断。"""

    orders = [
        Order("O-A", "C-1", OrderStatus.PENDING, Decimal("0.30"), "2026-01-01"),
        Order("O-B", "C-1", OrderStatus.PENDING, Decimal("0.29"), "2026-01-02"),
    ]
    result = filter_orders(orders, min_amount=Decimal("0.30"))
    assert [order.order_id for order in result] == ["O-A"]


def test_amount_filter_combines_with_status_filter(orders):
    """金额筛选与状态筛选同时存在时取交集，不改变原有筛选语义。"""

    result = filter_orders(orders, status=OrderStatus.PENDING, min_amount=Decimal("90.00"))
    assert [order.order_id for order in result] == ["O-1001", "O-1004"]


def test_orders_endpoint_supports_min_amount_query():
    """SPEC-API-001：查询接口接受 min_amount 并返回筛选后的结果。"""

    repository = InMemoryOrderRepository(load_orders_from_csv(DATA_FILE))
    server = create_server(repository, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/orders?min_amount=249.99", timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert payload["total"] == 3
    assert [order["order_id"] for order in payload["orders"]] == ["O-1004", "O-1006", "O-1007"]


def test_orders_endpoint_rejects_invalid_amount_query():
    """SPEC-API-001：非法金额参数必须返回 400，而不是静默忽略。"""

    repository = InMemoryOrderRepository(load_orders_from_csv(DATA_FILE))
    server = create_server(repository, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    try:
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"http://{host}:{port}/orders?min_amount=abc", timeout=10)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert excinfo.value.code == 400
