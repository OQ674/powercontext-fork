"""订单筛选。

职责：根据状态、金额区间等条件筛选订单，并按指定字段排序、分页。
金额区间筛选实现自 SPEC-ORD-003（闭区间，精确小数比较）。
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


def _coerce_amount(value: object, name: str) -> Optional[Decimal]:
    """把金额筛选条件规范化为 Decimal。

    只接受 ``Decimal`` 与 ``int``；字符串、浮点数、布尔值等一律拒绝，
    以免二进制浮点误差影响区间边界判断。
    """

    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be Decimal or int, got bool")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    raise ValueError(f"{name} must be Decimal or int, got {type(value).__name__}")


def filter_orders(
    orders: Iterable[Order],
    *,
    status: Optional[object] = None,
    min_amount: Optional[object] = None,
    max_amount: Optional[object] = None,
    sort_by: str = "created_at",
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> list[Order]:
    """筛选订单。

    参数:
        orders: 订单集合。
        status: 订单状态，``None`` 表示不过滤；支持 :class:`OrderStatus` 或状态字符串。
        min_amount: 金额下界（闭区间），``None`` 表示不设下界。
        max_amount: 金额上界（闭区间），``None`` 表示不设上界。
        sort_by: 排序字段，取值 ``created_at`` / ``amount`` / ``order_id``。
        offset: 偏移量，``None`` 表示不分页。
        limit: 返回条数，``None`` 表示不限制。

    返回:
        排序并分页后的订单列表。

    异常:
        ValueError: ``status`` 非法、``sort_by`` 非法、金额参数非法或
            ``min_amount`` 大于 ``max_amount`` 时抛出。
    """

    if sort_by not in SORT_KEYS:
        raise ValueError(f"unknown sort_by: {sort_by!r}, expected one of {SORT_KEYS}")

    wanted_status: Optional[OrderStatus] = None
    if status is not None:
        wanted_status = OrderStatus.parse(status)

    lower_bound = _coerce_amount(min_amount, "min_amount")
    upper_bound = _coerce_amount(max_amount, "max_amount")
    if lower_bound is not None and upper_bound is not None and lower_bound > upper_bound:
        raise ValueError(
            "min_amount must not be greater than max_amount: "
            f"min_amount={lower_bound}, max_amount={upper_bound}"
        )

    selected: list[Order] = []
    for order in orders:
        if wanted_status is not None and order.status != wanted_status:
            continue
        if lower_bound is not None and order.amount < lower_bound:
            continue
        if upper_bound is not None and order.amount > upper_bound:
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
