"""订单仓储。

演示工程使用 CSV 作为订单数据源，读取后转换为 :class:`Order` 列表。
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .models import Order, OrderStatus


class OrderRepository:
    """订单仓储接口。"""

    def all(self) -> list[Order]:
        """返回全部订单。"""

        raise NotImplementedError


class InMemoryOrderRepository(OrderRepository):
    """把订单保存在内存中的仓储实现。"""

    def __init__(self, orders: list[Order]) -> None:
        self._orders = list(orders)

    def all(self) -> list[Order]:
        return list(self._orders)


def load_orders_from_csv(path: str | Path) -> list[Order]:
    """从 CSV 文件读取订单。

    CSV 表头：``order_id,customer_id,status,amount,created_at``。
    """

    orders: list[Order] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            orders.append(
                Order(
                    order_id=row["order_id"],
                    customer_id=row["customer_id"],
                    status=OrderStatus.parse(row["status"]),
                    amount=Decimal(row["amount"]),
                    created_at=row["created_at"],
                )
            )
    return orders
