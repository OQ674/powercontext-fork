"""订单履约服务（演示业务工程）。

该包是本次验证样例使用的业务工程，提供订单查询、筛选、排序与阶梯折扣能力。
规格文档位于 ``specs/``，测试位于 ``tests/``。
"""

from .filters import filter_orders
from .models import Order, OrderStatus
from .pricing import discount_rate
from .repository import InMemoryOrderRepository, OrderRepository, load_orders_from_csv

__all__ = [
    "Order",
    "OrderStatus",
    "OrderRepository",
    "InMemoryOrderRepository",
    "load_orders_from_csv",
    "filter_orders",
    "discount_rate",
]

__version__ = "0.3.0"
