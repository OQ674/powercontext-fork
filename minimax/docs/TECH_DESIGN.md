# 一页技术说明（sddctx · 面向软件持续演进的 SDD 上下文管理系统）

## 1. 解决的问题

AI 开发助手改代码时需要三样东西：**当前应遵守的规格**、**应该改的代码**、**用哪些测试验证**；
并且在任务被打断后，需要能**读回上次进展**。本模块把这四件事做成一个可调用、可复核的工程化流程。

## 2. 模块结构

```
minimax/
├── sddctx/                     上下文模块（Python 包，入口 python -m sddctx）
│   ├── config.py               配置（SDDCTX_* 环境变量 / --config 文件）
│   ├── db.py                   seekdb/OceanBase 访问层（PyMySQL，嵌入式或 Server 模式）
│   ├── schema.py               8 张表：规格 / 代码符号 / 测试 / 任务 / 进展 / 验证 / 检索 / SQL 日志
│   ├── importer.py             规格、代码符号（ast）、测试用例（pytest node id）的导入与版本化
│   ├── retriever.py            关键词切分 + 三路 SQL 召回（规格 / 代码 / 测试）
│   ├── context.py              上下文包组装（JSON + Markdown），每条都带真实来源
│   ├── powercontext_client.py  PowerContext HTTP 客户端（Scope / Memory 读写）
│   ├── state.py                任务状态存取（PowerContext 为主，seekdb 镜像兜底）
│   ├── agent.py                MiniMax 接入：在线调用 API / 离线回放已留档补丁
│   ├── patcher.py              统一 diff 应用器（不依赖 git / patch）
│   ├── verify.py               pytest 执行与结果解析
│   └── cli.py                  命令行入口（11 个子命令）
├── sample_project/             业务工程（订单履约服务）：specs/ + src/ + tests/ + data/
├── scripts/                    run_demo.sh / reset_demo.sh / spec_update_demo.sh / start_powercontext.sh
├── artifacts/                  上下文包、MiniMax 补丁与开发记录、PowerContext 状态记录、修改前快照
├── logs/                       修改前后测试日志、模块自测日志、数据库查询与检索记录
└── docs/                       RUNBOOK / VALIDATION_SAMPLE / TECH_DESIGN
```

## 3. 上下文选择方式（为什么选出来的就是该改的）

1. **关键词切分**：任务标题 + 描述 → 标识符整体保留（`min_amount`）、中文按二元组切分（`金额`、`区间`）。
2. **候选筛选在数据库完成**：对 `sdd_spec_item` / `sdd_code_symbol` / `sdd_test_case` 执行真实
   `LIKE` 检索 SQL（`WHERE … OR …` + `LIMIT`），SQL 与命中项写入 `sdd_retrieval_log`。
3. **优先级规则**：
   * 规格里显式声明的**关联代码 / 关联测试**权重最高（+5 分）——这是 SDD 的"可追溯"保证；
   * 关键词命中次之；同文件测试再 +1 分。
4. **来源真实存在**：每条规格带 `source_file` + `revision`，每条代码带 `file_path` + 行号 +
   签名，每条测试带 pytest `node_id`，全部可在仓库中核对。
5. **规格可演进**：规格按内容哈希版本化，重新导入时 `revision` 自增；规格更新后同一任务召回的是
   **新版本正文**（`scripts/spec_update_demo.sh` 演示）。

## 4. 三项技术的分工

| 技术 | 承担的作用 | 在流程中的位置 | 可核对证据 |
| --- | --- | --- | --- |
| **seekdb**（OceanBase seekdb 1.4.0，MySQL 协议） | 存储工程资料与索引，检索结果用于构造上下文 | 导入 → 召回 → 记录 | `logs/db_query_log.md`（全部 SQL）、`sdd_query_log` / `sdd_retrieval_log` 表 |
| **MiniMax**（MiniMax-M3.1-Flash，MiniMax Code Agent） | 参与本次任务的代码生成/修改 | 上下文 → 提示词 → 补丁 → 应用 | `artifacts/minimax_dev_log.jsonl`（任务、上下文、提示词、模型响应、哈希）、`artifacts/minimax_patch.diff` |
| **PowerContext**（1.5.1，HTTP API） | 保存任务进展与验证结果，并在后续运行中读取使用 | 状态写入 → **新进程**读取 → 进入下一次上下文 | `artifacts/powercontext_state_log.md`、`logs/` 下的状态输出 |

> 接入方式与版本：
> * seekdb：嵌入式 `pylibseekdb==1.4.0.post2`（引擎自带，Unix socket 暴露 MySQL 协议），也支持
>   `SDDCTX_DB_MODE=server` 直连 seekdb/OceanBase Server。
> * MiniMax：OpenAI 兼容接口 `POST {base}/chat/completions`（`SDDCTX_MINIMAX_API_KEY`）；
>   本次记录使用**离线回放**，回放内容即本次会话中 MiniMax 针对同一提示词生成的补丁。
> * PowerContext：HTTP API（`/v1/scopes`、`/v1/memory/remember`、`/v1/atomic-memory/list`），
>   服务端使用本地 SQLite，无需任何模型 API。

## 5. 端到端流程

```
规格/代码/测试 ──import──▶ seekdb（索引 + 版本）
                              │
任务描述 ──recall(SQL)───────▶ 上下文包（规格 + 代码符号 + 测试 + 历史状态）
                              │                       │
                              │                       ▼
                              │                 MiniMax（生成补丁）
                              │                       │
                              │                  apply diff
                              │                       ▼
                              │                 pytest（目标功能 + 回归）
                              │                       │
                              └──state-save──────────▶ PowerContext（任务状态）
                                                        │ 新进程
                                                        ▼
                                              state-show / context --include-state
```

## 6. 边界与取舍

* 检索为**词法召回**（关键词 + 规格显式关联），未使用向量检索：当前环境没有可用的 Embedding 服务，
  接入 seekdb 向量索引的接口已预留（`sdd_code_symbol` / `sdd_spec_item` 预留向量列位）。
* 状态条目用 `[任务ID][类型] 内容` 前缀编码，使 PowerContext 退化为纯文本检索时仍可稳定读回。
* 补丁应用自实现统一 diff 解析，避免依赖 git / patch 命令，保证在任意评审环境可复现。
