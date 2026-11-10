# SPEC-ORD-002 订单状态筛选

- 规格 ID：SPEC-ORD-002
- 状态：生效
- 所属模块：order_fulfillment.filters
- 关联代码：src/order_fulfillment/filters.py::filter_orders
- 关联测试：tests/test_filters.py
- 关键词：状态筛选, status, 待发货, 已发货

## 需求

`filter_orders` 必须支持按订单状态筛选，状态取值来自 `OrderStatus` 枚举。

## 验收标准

1. `status=None` 表示不过滤状态。
2. 传入 `OrderStatus` 时只返回该状态的订单。
3. 传入非法状态字符串时抛出 `ValueError`，错误信息包含原始取值。
4. 状态筛选与其它筛选条件同时存在时，结果为各条件交集。

## 不在范围内

- 不做状态流转，仅做筛选。
