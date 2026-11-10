"""订单领域模型。

该模块定义订单查询链路上的基础数据结构：订单、订单状态。
金额统一使用 ``decimal.Decimal`` 表达，避免二进制浮点误差影响边界判断。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class OrderStatus(str, Enum):
    """订单状态。"""

    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    @classmethod
    def parse(cls, raw: object) -> "OrderStatus":
        """把外部输入解析为 ``OrderStatus``。

        非法取值抛出 ``ValueError``，错误信息中包含原始取值。
        """

        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            try:
                return cls(raw.strip().lower())
            except ValueError:
                raise ValueError(f"invalid order status: {raw!r}") from None
        raise ValueError(f"invalid order status: {raw!r}")


@dataclass(frozen=True)
class Order:
    """一条订单记录。"""

    order_id: str
    customer_id: str
    status: OrderStatus
    amount: Decimal
    created_at: str

    def to_dict(self) -> dict:
        """转换为接口返回用的字典，金额保留两位小数字符串。"""

        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "status": self.status.value,
            "amount": f"{self.amount:.2f}",
            "created_at": self.created_at,
        }
