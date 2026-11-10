"""阶梯折扣计算（SPEC-PRC-001）。"""

from __future__ import annotations

from decimal import Decimal

TIERS = (
    (Decimal("500"), Decimal("0.90")),
    (Decimal("100"), Decimal("0.95")),
)


def discount_rate(amount: Decimal) -> Decimal:
    """根据订单金额返回折扣率。

    金额低于 100 元返回 ``1.00``，100~500 元返回 ``0.95``，500 元及以上返回 ``0.90``。
    """

    if not isinstance(amount, Decimal):
        raise ValueError(f"amount must be Decimal, got {type(amount).__name__}")
    for threshold, rate in TIERS:
        if amount >= threshold:
            return rate
    return Decimal("1.00")
