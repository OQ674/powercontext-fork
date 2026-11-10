# SPEC-PRC-001 阶梯折扣计算

- 规格 ID：SPEC-PRC-001
- 状态：生效
- 所属模块：order_fulfillment.pricing
- 关联代码：src/order_fulfillment/pricing.py::discount_rate
- 关联测试：tests/test_pricing.py
- 关键词：折扣, 阶梯, discount_rate

## 需求

根据订单金额计算阶梯折扣率，折扣率以 `Decimal` 返回。

## 验收标准

1. 金额低于 100 元时折扣率为 `Decimal("1.00")`。
2. 金额大于等于 100 元且低于 500 元时折扣率为 `Decimal("0.95")`。
3. 金额大于等于 500 元时折扣率为 `Decimal("0.90")`。
4. 计算过程使用 `Decimal`，不接受二进制浮点入参。

## 不在范围内

- 不做优惠券叠加计算。
