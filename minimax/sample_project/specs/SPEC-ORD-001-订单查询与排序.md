# SPEC-ORD-001 订单查询与排序

- 规格 ID：SPEC-ORD-001
- 状态：生效
- 所属模块：order_fulfillment.filters
- 关联代码：src/order_fulfillment/filters.py::filter_orders
- 关联测试：tests/test_filters.py
- 关键词：排序, sort_by, created_at, amount, 分页

## 需求

`filter_orders` 在完成筛选后必须按指定字段排序，并支持分页。

## 验收标准

1. `sort_by` 支持 `created_at`（默认）、`amount`、`order_id`。
2. 排序方向为升序；金额排序使用精确小数比较。
3. `offset` 与 `limit` 为 `None` 时返回全部结果；`limit <= 0` 时抛出 `ValueError`。
4. 任何新增筛选条件都不得改变上述排序与分页语义。

## 不在范围内

- 不支持降序排序参数。
