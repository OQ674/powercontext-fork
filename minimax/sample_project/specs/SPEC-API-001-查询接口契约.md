# SPEC-API-001 订单查询 HTTP 接口契约

- 规格 ID：SPEC-API-001
- 状态：生效
- 所属模块：order_fulfillment.service
- 关联代码：src/order_fulfillment/service.py::OrderQueryHandler
- 关联测试：tests/test_service_api.py
- 关键词：HTTP, 查询接口, /orders, 查询参数

## 需求

订单查询服务对外提供 `GET /orders` 接口，返回 JSON 格式的订单列表。

## 验收标准

1. `GET /orders` 返回 `200`，响应体为 `{"orders": [...], "total": <int>}`。
2. 支持的查询参数：`status`、`min_amount`、`max_amount`、`sort_by`、`offset`、`limit`。
3. `min_amount` / `max_amount` 与 `filter_orders` 语义一致，非法取值返回 `400` 并给出错误信息。
4. 接口响应中的 `amount` 字段保留两位小数字符串表示。

## 不在范围内

- 不提供写操作接口。
