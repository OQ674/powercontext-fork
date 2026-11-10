"""订单筛选。

职责：根据状态等条件筛选订单，并按指定字段排序、分页。
金额区间筛选（SPEC-ORD-003）尚未实现，见 specs/SPEC-ORD-003-订单金额区间筛选.md。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional, Sequence

from .models import Order, OrderStatus

SORT_KEYS = ("created_at", "amount", "order_id")


def _sort_value(order: Order, sort_by: str):
    if sort_by == "created_at":
        return order.created_at
    if sort_by == "amount":
        return order.amount
    if sort_by == "order_id":
        return order.order_id
    raise ValueError(f"unknown sort_by: {sort_by!r}, expected one of {SORT_KEYS}")


def filter_orders(
    orders: Iterable[Order],
    *,
    status: Optional[object] = None,
    sort_by: str = "created_at",
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> list[Order]:
    """筛选订单。

    参数:
        orders: 订单集合。
        status: 订单状态，``None`` 表示不过滤；支持 :class:`OrderStatus` 或状态字符串。
        sort_by: 排序字段，取值 ``created_at`` / ``amount`` / ``order_id``。
        offset: 偏移量，``None`` 表示不分页。
        limit: 返回条数，``None`` 表示不限制。

    返回:
        排序并分页后的订单列表。

    异常:
        ValueError: ``status`` 非法、``sort_by`` 非法或 ``limit`` 非正数时抛出。
    """

    if sort_by not in SORT_KEYS:
        raise ValueError(f"unknown sort_by: {sort_by!r}, expected one of {SORT_KEYS}")

    wanted_status: Optional[OrderStatus] = None
    if status is not None:
        wanted_status = OrderStatus.parse(status)

    selected: list[Order] = []
    for order in orders:
        if wanted_status is not None and order.status != wanted_status:
            continue
        selected.append(order)

    selected.sort(key=lambda item: _sort_value(item, sort_by))

    if offset is None and limit is None:
        return selected

    start = 0 if offset is None else offset
    if start < 0:
        raise ValueError(f"offset must not be negative: {offset}")
    if limit is not None and limit <= 0:
        raise ValueError(f"limit must be positive: {limit}")
    end = None if limit is None else start + limit
    return selected[start:end]
