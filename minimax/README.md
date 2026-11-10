# MiniMax 赛题作品：面向软件持续演进的 SDD 上下文管理系统

本目录是 **MiniMax × OceanBase** 赛题的完整参赛材料：面向 AI 开发助手的工程上下文模块
`sddctx`，并附一次完整的"导入资料 → 检索上下文 → MiniMax 改代码 → 跑测试 → 保存并复用任务状态"
验证记录。

## 目录导航

| 路径 | 内容 |
| --- | --- |
| `docs/RUNBOOK.md` | **运行说明**：依赖版本、配置、初始化、调用入口、测试命令、已知限制 |
| `docs/VALIDATION_SAMPLE.md` | **验证样例**：任务描述、有效规格、初始数据、操作步骤、预期结果、重置方法 |
| `docs/TECH_DESIGN.md` | **一页技术说明**：模块结构、上下文选择方式、三项技术的分工 |
| `sddctx/` | **完整源码**：上下文模块（CLI、数据库层、召回、上下文组装、Agent 接入、测试执行） |
| `sample_project/` | **业务工程**（订单履约服务）：`specs/` 规格、`src/` 代码、`tests/` 测试、`data/` 数据 |
| `scripts/` | 一键脚本：验证样例、重置、规格变更演示、PowerContext 启动 |
| `artifacts/` | 上下文包、MiniMax 提示词与补丁、MiniMax 开发记录、PowerContext 状态读回记录、修改前代码快照 |
| `logs/` | 修改前后测试日志、模块自测日志、seekdb 查询与检索记录 |
| `tests/` | 模块自身的单元测试 |

## 三项指定技术的落点

| 技术 | 作用 | 证据 |
| --- | --- | --- |
| **MiniMax** | 参与本次任务的代码生成/修改 | `artifacts/minimax_dev_log.jsonl`、`artifacts/minimax_patch.diff` |
| **seekdb / OceanBase** | 存储工程资料与索引，检索结果用于构造上下文 | `logs/db_query_log.md`（全部 SQL 与命中项） |
| **PowerContext** | 保存任务进展与验证结果，新进程读取并使用 | `artifacts/powercontext_state_log.md` |

## 快速开始

```bash
cd minimax
pip install "powercontext[server,cli]==1.5.1" "pylibseekdb==1.4.0.post2" \
            "PyMySQL==1.2.3" "pytest==9.2.0"

# 终端 A：启动 PowerContext（保存 / 复用任务状态）
bash scripts/start_powercontext.sh

# 终端 B：执行验证样例（建库 → 导入 → 上下文 → 改码 → 测试 → 存状态 → 重启复用）
bash scripts/run_demo.sh
```

完整说明见 `docs/RUNBOOK.md`。
