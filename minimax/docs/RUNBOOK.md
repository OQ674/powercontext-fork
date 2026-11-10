# 运行说明（sddctx · SDD 上下文管理模块）

本文件说明如何在**干净环境**中安装依赖、初始化数据、启动模块并执行验证样例。
所有命令都在仓库的 `minimax/` 目录下执行。

---

## 1. 依赖与版本

| 组件 | 版本 | 用途 | 安装方式 |
| --- | --- | --- | --- |
| Python | 3.11+（本次记录使用 3.12.3） | 运行模块与业务工程测试 | `python3 --version` |
| PowerContext | 1.5.1（PyPI `powercontext[server,cli]`） | 保存并复用任务状态 | `pip install "powercontext[server,cli]==1.5.1"` |
| pylibseekdb | 1.4.0.post2（PyPI `pylibseekdb`） | 嵌入式 seekdb 引擎 | `pip install "pylibseekdb==1.4.0.post2"` |
| PyMySQL | 1.2.3 | 通过 MySQL 协议访问 seekdb / OceanBase | `pip install "PyMySQL==1.2.3"` |
| pytest | 9.2.0 | 业务工程测试与模块自测 | `pip install "pytest==9.2.0"` |

> 数据库接入方式二选一：
> * **嵌入式 seekdb（默认，Linux/macOS）**：`pylibseekdb` 自带引擎，数据落在 `SDDCTX_SEEKDB_DIR` 目录，
>   通过 Unix socket 暴露 MySQL 协议，模块用 PyMySQL 连接。
>   如还需要向量 / Embedding 等客户端能力，可额外安装 `pyseekdb==1.4.0.post1`（会带入 onnxruntime，
>   本作品不需要）。
> * **seekdb / OceanBase Server（Windows 或已有实例）**：设置 `SDDCTX_DB_MODE=server` 与
>   `SDDCTX_DB_HOST/SDDCTX_DB_PORT/SDDCTX_DB_USER/SDDCTX_DB_PASSWORD`，
>   模块同样用 MySQL 协议连接，SQL 完全一致。
>
> 本次记录使用嵌入式 seekdb，服务端版本串为 `5.7.25-OceanBase seekdb-v1.4.0.0`。

一次性安装：

```bash
cd minimax
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 等价于：
# pip install "powercontext[server,cli]==1.5.1" "pylibseekdb==1.4.0.post2" \
#             "PyMySQL==1.2.3" "pytest==9.2.0"
```

> PowerContext 的 CLI 依赖 `typer`（`[cli]` extra），`server run` 需要它；
> 若只使用本模块的 HTTP 客户端，`powercontext[server]` 即可。

## 2. 配置

模块所有配置项都可用环境变量覆盖（也可用 `--config` 指定 `KEY=VALUE` 文件）：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SDDCTX_PROJECT_ROOT` | 当前目录 | 工程根目录（`minimax/`） |
| `SDDCTX_DB_MODE` | `embedded` | `embedded` 或 `server` |
| `SDDCTX_SEEKDB_DIR` | `<root>/.sddctx/seekdb` | 嵌入式 seekdb 数据目录 |
| `SDDCTX_DB_HOST` / `SDDCTX_DB_PORT` | `127.0.0.1` / `2881` | Server 模式连接地址 |
| `SDDCTX_DB_USER` / `SDDCTX_DB_PASSWORD` | `root` / 空 | Server 模式账号 |
| `SDDCTX_DB_NAME` | `sddctx` | 业务库名 |
| `SDDCTX_POWERCONTEXT_URL` | `http://127.0.0.1:8000` | PowerContext Server 地址 |
| `SDDCTX_POWERCONTEXT_SCOPE` | `sdd-context-module` | 任务状态所在 Scope 的标题 |
| `SDDCTX_MINIMAX_API_KEY` | 空 | 配置后在线调用 MiniMax 生成补丁 |
| `SDDCTX_MINIMAX_BASE_URL` | `https://api.minimax.chat/v1` | MiniMax 接口地址 |
| `SDDCTX_MINIMAX_MODEL` | `MiniMax-M2` | 使用的 MiniMax 模型 |

## 3. 启动 PowerContext（保存/复用任务状态）

```bash
cd minimax
bash scripts/start_powercontext.sh          # 前台启动，日志输出到当前终端
# 或自行生成环境文件后启动：
#   powercontext server run --env-file .sddctx/powercontext/.env
```

该脚本生成 `.sddctx/powercontext/.env`（SQLite 存储、关闭鉴权、无需任何模型 API），
数据库文件为 `.sddctx/powercontext/powercontext.db`。健康检查：

```bash
curl -s http://127.0.0.1:8000/health/ready
```

## 4. 初始化数据与执行验证样例

```bash
cd minimax
bash scripts/run_demo.sh
```

该脚本按顺序完成 10 步（0/9 ~ 9/9），第 0 步先把业务工程还原到"修改前"，因此可从零复现：

| 步骤 | 命令 | 产出 |
| --- | --- | --- |
| 0/9 | `bash scripts/reset_demo.sh` | 还原 `filters.py` / `service.py` 为修改前状态 |
| 1/9 | `python -m sddctx db-init` | 8 张表（`sdd_spec_item` 等） |
| 2/9 | `python -m sddctx import --kind all` | 5 条规格、18 个代码符号、35 个测试用例 |
| 3/9 | `python -m sddctx context …` | `artifacts/context_before.json` / `.md` |
| 4/9 | `python -m sddctx verify --phase before …` | `logs/pytest_before_feature.log`（目标功能测试失败） |
| 5/9 | `python -m sddctx agent-patch … --apply` | `artifacts/minimax_patch.diff` + 应用结果 + 开发记录 |
| 6/9 | `python -m sddctx verify --phase after-feature …` / `--phase after …` | `logs/pytest_after_feature.log`、`logs/pytest_after.log` |
| 7/9 | `python -m sddctx state-save …` | 任务状态写入 PowerContext |
| 8/9 | `python -m sddctx state-show` / `state-log` / `context --include-state` | **新进程**读取并使用已保存状态 |
| 9/9 | `python -m sddctx evidence` | `logs/db_query_log.md` |

单步执行（便于调试）：

```bash
python -m sddctx doctor                     # 检查数据库与 PowerContext 连通性
python -m sddctx db-init
python -m sddctx import --kind all
python -m sddctx context --task-id TASK-ORD-003 \
    --title "为订单查询增加金额区间筛选" \
    --description "在 filter_orders 上新增 min_amount / max_amount 闭区间金额筛选，使用 Decimal 精确比较" \
    --include-state --out artifacts/context_before.json --markdown-out artifacts/context_before.md
python -m sddctx verify --task-id TASK-ORD-003 --phase before \
    --target tests/test_feature_amount_filter.py --log logs/pytest_before_feature.log
python -m sddctx agent-patch --task-id TASK-ORD-003 \
    --context artifacts/context_before.json --patch-file artifacts/minimax_patch.diff --apply
python -m sddctx verify --task-id TASK-ORD-003 --phase after --target tests --log logs/pytest_after.log
python -m sddctx state-save --task-id TASK-ORD-003 --done "…" --todo "…" --verification "phase=after | …"
python -m sddctx state-show --task-id TASK-ORD-003
python -m sddctx evidence --out logs/db_query_log.md
```

规格变更演示（证明上下文不是固定答案）：

```bash
bash scripts/spec_update_demo.sh      # 用 specs_v2 覆盖 SPEC-ORD-003 → 重新导入 → 上下文出现第 2 版
```

## 5. 测试命令

```bash
# 业务工程（目标功能测试 + 回归测试）
cd sample_project && python -m pytest -q

# 业务工程：仅目标功能测试
cd sample_project && python -m pytest -q tests/test_feature_amount_filter.py

# 业务工程：仅回归测试（修改前后都应通过）
cd sample_project && python -m pytest -q tests/test_filters.py tests/test_pricing.py \
                                     tests/test_repository.py tests/test_service_api.py

# 模块自身单元测试
cd minimax && python -m pytest -q tests
```

## 6. 已知限制

1. **嵌入式 seekdb 仅支持 Linux / macOS**：Windows 上 `pylibseekdb` 不可用，请改用
   `SDDCTX_DB_MODE=server` 连接 seekdb / OceanBase Server（安装包：`seekdb-*-win64.msi`）。
2. **嵌入式 seekdb 的数据目录必须位于本地文件系统**：在 WSL 中若工程放在 `/mnt/d/...` 等
   挂载盘上，请把 `SDDCTX_SEEKDB_DIR` 指向 Linux 原生路径（例如 `/root/.sddctx/seekdb`）。
3. **PowerContext 的 Windows 支持为 experimental**，官方推荐 macOS / Linux；
   本次记录全部在 Linux（WSL2 Ubuntu 24.04）上完成。
4. **离线回放模式**：未配置 `SDDCTX_MINIMAX_API_KEY` 时，`agent-patch` 会回放
   `artifacts/minimax_patch.diff`（本次任务中由 MiniMax 生成的补丁），并在开发记录中标注
   `mode=replay`；配置 Key 后同一命令会真实调用 MiniMax 接口（`mode=online`）。
5. **上下文召回以关键词命中为主**：模块不做向量检索（当前环境没有可用的 Embedding 服务）；
   规格里声明的"关联代码/关联测试"是优先级最高的来源，关键词命中只用于补充与排序。
