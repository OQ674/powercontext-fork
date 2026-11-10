# SPEC-ORD-003 订单金额区间筛选

- 规格 ID：SPEC-ORD-003
- 状态：生效
- 所属模块：order_fulfillment.filters
- 关联代码：src/order_fulfillment/filters.py::filter_orders
- 关联测试：tests/test_feature_amount_filter.py
- 关键词：金额筛选, min_amount, max_amount, 区间, 闭区间, ValueError

## 需求

`filter_orders` 必须支持按订单金额区间筛选订单。筛选条件通过关键字参数 `min_amount` 与 `max_amount`
传入，二者共同构成一个**闭区间** `[min_amount, max_amount]`。

## 验收标准

1. `min_amount` 与 `max_amount` 均为 `None` 时，金额维度不做任何过滤，行为与既有版本完全一致。
2. 只传 `min_amount` 时，返回所有 `amount >= min_amount` 的订单；只传 `max_amount` 时，返回所有
   `amount <= max_amount` 的订单。
3. 同时传入两个参数时，返回 `min_amount <= amount <= max_amount` 的订单（闭区间，两端都包含）。
4. `min_amount > max_amount` 属于参数错误，必须抛出 `ValueError`，且错误信息中包含 `min_amount` 与
   `max_amount` 两个参数名。
5. `min_amount` / `max_amount` 只接受 `decimal.Decimal` 或 `int` 取值；字符串、浮点数、布尔值等
   其它类型必须抛出 `ValueError`（浮点数被显式拒绝，因为二进制浮点无法保证边界精度）。
   `None` 表示该侧不设边界，不是非法取值。
6. 金额比较必须使用精确小数运算（`decimal.Decimal`），禁止使用二进制浮点数直接比较，
   以免 `0.1 + 0.2` 类误差导致边界订单被错误排除。
7. 边界金额（例如恰好等于 `min_amount` 或 `max_amount`）的订单必须被保留。

## 不在范围内

- 不改变 `status` 筛选、`sort_by` 排序与分页的既有语义。
- 不改变 `Order` 数据模型与 CSV 数据文件结构。
