# 验证样例（sddctx · SDD 上下文管理模块）

本样例可在干净环境按 `docs/RUNBOOK.md` 完整复现：一条命令 `bash scripts/run_demo.sh`
即可从空状态跑到"重启后复用状态"。

---

## 1. 任务描述

* **任务 ID**：`TASK-ORD-003`
* **标题**：为订单查询增加金额区间筛选
* **描述**：在订单筛选函数 `filter_orders` 上新增 `min_amount` / `max_amount` 闭区间金额筛选，
  金额使用 `Decimal` 精确比较；必须保持既有状态筛选、排序与分页行为不变，并让新增的目标功能测试通过。
* **要改什么**：订单筛选函数与订单查询 HTTP 接口的金额筛选能力。
* **哪些原有行为必须保持**：状态筛选语义、排序字段与排序方向、分页语义、CSV 数据结构、
  折扣计算逻辑全部不变（见下文"必须保持的行为"）。

## 2. 有效规格（上下文必须包含的来源）

| 规格 ID | 标题 | 来源文件 | 与本任务的关系 |
| --- | --- | --- | --- |
| `SPEC-ORD-003` | 订单金额区间筛选 | `sample_project/specs/SPEC-ORD-003-订单金额区间筛选.md` | **目标规格**：定义 `min_amount`/`max_amount` 的 7 条验收标准 |
| `SPEC-ORD-002` | 订单状态筛选 | `sample_project/specs/SPEC-ORD-002-订单状态筛选.md` | 既有行为，必须保持 |
| `SPEC-ORD-001` | 订单查询与排序 | `sample_project/specs/SPEC-ORD-001-订单查询与排序.md` | 既有行为，必须保持（含"任何新增筛选条件都不得改变排序与分页语义"） |
| `SPEC-API-001` | 订单查询 HTTP 接口契约 | `sample_project/specs/SPEC-API-001-查询接口契约.md` | 接口层需透传金额参数，非法取值返回 400 |
| `SPEC-PRC-001` | 阶梯折扣计算 | `sample_project/specs/SPEC-PRC-001-折扣计算.md` | 既有行为，必须保持 |

规格条目在上下文中必须包含：规格 ID、标题、**来源文件路径**、**版本号**、状态、
"关联代码"、"关联测试"以及正文全文（见 `artifacts/context_before.md` 第一节）。

## 3. 必须出现在上下文中的代码与测试来源

| 类型 | 来源 | 说明 |
| --- | --- | --- |
| 代码 | `src/order_fulfillment/filters.py::filter_orders` | 目标函数（`SPEC-ORD-003` 关联代码） |
| 代码 | `src/order_fulfillment/service.py::OrderQueryHandler` / `create_server` | 接口透传金额参数 |
| 代码 | `src/order_fulfillment/models.py::Order` / `OrderStatus` | 数据模型（不修改） |
| 测试 | `tests/test_feature_amount_filter.py`（12 个用例） | **目标功能测试**，`SPEC-ORD-003` 关联测试 |
| 测试 | `tests/test_filters.py`（10 个用例） | 回归测试：状态筛选 / 排序 / 分页 |
| 测试 | `tests/test_pricing.py`（5 个用例） | 回归测试：阶梯折扣 |
| 测试 | `tests/test_repository.py`（5 个用例） | 回归测试：CSV 仓储 |
| 测试 | `tests/test_service_api.py`（5 个用例） | 回归测试：HTTP 接口 |

## 4. 初始数据

* 订单数据：`sample_project/data/orders.csv`（8 条订单，金额含 `99.99` / `100.00` / `199.50` /
  `500.00` / `0.30` / `249.99` / `1200.75` / `89.90` 等边界值，状态覆盖 4 种）。
* 数据库：首次运行由 `python -m sddctx db-init` 建表（8 张表），初始为空。
* 任务状态：**从空状态开始**（PowerContext 中该 Scope 下没有任何状态条目）。

## 5. 操作步骤（`bash scripts/run_demo.sh`）

`bash scripts/run_demo.sh` 共 10 步（0/9 ~ 9/9），第 0 步先把业务工程还原到"修改前"，
因此整条链路可以从零复现，无需人工干预。

| 步 | 命令 | 预期 |
| --- | --- | --- |
| 0/9 | `bash scripts/reset_demo.sh` | 把 `filters.py` / `service.py` 还原为"修改前"副本（来自 `artifacts/before_snapshot/`） |
| 1/9 | `python -m sddctx db-init` | 建表成功，输出数据库后端与版本 |
| 2/9 | `python -m sddctx import --kind all` | 导入 5 条规格、18 个代码符号、35 个测试用例 |
| 3/9 | `python -m sddctx context --task-id TASK-ORD-003 … --include-state` | 生成上下文包：规格 / 代码 / 测试 / 状态四部分齐全，且每条都带真实来源 |
| 4/9 | `python -m sddctx verify --phase before --target tests/test_feature_amount_filter.py` | **失败**：目标功能尚未实现（`TypeError: unexpected keyword argument 'min_amount'` 等），退出码非 0 |
| 5/9 | `python -m sddctx agent-patch --context artifacts/context_before.json --patch-file artifacts/minimax_patch.diff --apply` | 应用 MiniMax 补丁；开发记录写入 `artifacts/minimax_dev_log.jsonl` |
| 6/9 | `python -m sddctx verify --phase after-feature --target tests/test_feature_amount_filter.py` | 目标功能测试**全部通过** |
| 6/9 | `python -m sddctx verify --phase after --target tests` | **全部通过**（目标功能 + 回归） |
| 7/9 | `python -m sddctx state-save --task-id TASK-ORD-003 --done … --todo … --verification …` | 状态写入 PowerContext（Scope `sdd-context-module`） |
| 8/9 | `python -m sddctx state-show --task-id TASK-ORD-003` | **新进程**读回状态：已完成 / 待办 / 验证结果齐全，来源 `powercontext:<scope_id>` |
| 8/9 | `python -m sddctx state-log --task-id TASK-ORD-003 --out artifacts/powercontext_state_log.md` | 导出状态读回记录 |
| 8/9 | `python -m sddctx context … --include-state` | 上下文的第四节包含历史状态 |
| 9/9 | `python -m sddctx evidence --out logs/db_query_log.md` | 导出 `logs/db_query_log.md` |

> 步骤 3 与 8 中的 `context` 命令均在**独立进程**中执行，第 8 步的进程从 PowerContext
> 读回第 7 步保存的状态，从而证明"重启后状态可复用"。

## 6. 预期结果

1. **上下文正确**：上下文包中包含 `SPEC-ORD-003` 等 5 条规格（含来源文件与版本号）、
   `filter_orders` 等代码符号（含文件路径与行号）、目标功能测试与回归测试的 pytest node id；
   规格更新并重新导入后，召回的是**新版本正文**（`bash scripts/spec_update_demo.sh` 演示）。
2. **数据库实际参与**：导入写入 5 + 18 + 35 行；召回执行真实 `LIKE` 检索 SQL；
   `logs/db_query_log.md` 记录每条 SQL 与命中项。
3. **MiniMax 实际参与**：`artifacts/minimax_dev_log.jsonl` 记录任务、上下文来源、提示词、
   模型响应（补丁）与哈希；`artifacts/minimax_patch.diff` 与最终代码差异一致。
4. **代码修改有效**：同一组目标功能测试修改前失败、修改后通过；回归测试修改前后均通过。
5. **状态能够复用**：从空状态保存 → **重启模块**（新进程）→ 读回并用于后续上下文。
   `state-save` 是**幂等**的：同一条 `[任务ID][类型] 内容` 重复写入会被跳过
   （返回 `written: []` / `skipped: [...]`），因此反复执行验证样例不会在
   PowerContext 中累积重复条目，读回的仍是干净的 7 条状态。

## 7. 重置方法

```bash
cd minimax

# 1) 业务工程恢复到"修改前"
bash scripts/reset_demo.sh                 # 还原 filters.py / service.py

# 2) 可选：清空本地 seekdb 数据（下次 db-init 会重新建表）
RESET_DB=1 bash scripts/reset_demo.sh

# 3) 可选：清空 PowerContext 状态
#    停止 PowerContext 服务后删除 .sddctx/powercontext/powercontext.db，再重新启动
```

## 8. 修改前后对照

| 项目 | 修改前 | 修改后 |
| --- | --- | --- |
| `filter_orders` 签名 | 无 `min_amount` / `max_amount` | 新增两个可选关键字参数 |
| 金额比较 | 不支持 | `Decimal` 精确比较，闭区间 |
| 非法金额参数 | 不适用 | 抛 `ValueError`（含两个参数名） |
| HTTP 接口 | 接受但忽略 `min_amount` | 解析为 `Decimal` 并透传，非法取值返回 400 |
| 目标功能测试（12 项） | 11 失败 / 1 通过 | **12 通过** |
| 回归测试（25 项） | 25 通过 | **25 通过** |

## 9. 本次记录的实际结果

环境：WSL2 Ubuntu 24.04 / Python 3.12.3 / PowerContext 1.5.1 / 嵌入式 seekdb
（`5.7.25-OceanBase seekdb-v1.4.0.0`）/ PyMySQL 1.2.3 / pytest 9.2.0。

| 检查项 | 实际结果 | 证据文件 |
| --- | --- | --- |
| 建表 | 8 张表创建成功 | `logs/db_query_log.md` |
| 导入 | 5 条规格、6 个代码文件 / 18 个符号、5 个测试文件 / 35 个用例 | `logs/db_query_log.md` |
| 上下文 | 5 条规格 + 8 个代码符号 + 12 个测试用例，25 条引用来源 | `artifacts/context_before.md` |
| 修改前目标功能测试 | 退出码 1，**1 通过 / 11 失败**（`TypeError: filter_orders() got an unexpected keyword argument 'min_amount'`） | `logs/pytest_before_feature.log` |
| 修改后目标功能测试 | 退出码 0，**12 通过 / 0 失败** | `logs/pytest_after_feature.log` |
| 修改后全部测试 | 退出码 0，**37 通过 / 0 失败**（12 功能 + 25 回归） | `logs/pytest_after.log` |
| 模块自测 | 退出码 0，**6 通过 / 0 失败** | `logs/pytest_module.log` |
| MiniMax 参与 | `mode=replay`，模型 `MiniMax-M3.1-Flash (MiniMax Code agent)`，补丁应用到 `filters.py` 与 `service.py`；`recorded_prompt_matches_context=True` | `artifacts/minimax_dev_log.jsonl`、`artifacts/minimax_patch.diff` |
| 数据库参与 | 101 条 SQL 记录（50 条检索命中、3 条测试记录） | `logs/db_query_log.md` |
| 状态保存与复用 | Scope `scp_7nd99vvkpwf1h06q9hgpaxg50e` 下 7 条记忆；**新进程**读回并写入下一次上下文 | `artifacts/powercontext_state_log.md`、`artifacts/context_after.md` |
| 规格变更 | `SPEC-ORD-003` 升到第 2 版，关键词新增 `Decimal, 精确十进制`，正文新增第 8 条验收标准 | `artifacts/context_after_spec_update.md` |

> 上述 Scope ID、条数等为本次运行的具体取值；重新执行时 ID 会变化，流程与结论不变。
