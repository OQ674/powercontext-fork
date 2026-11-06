> 现状说明（提交前请读）：**seekdb + PowerContext + bridge + Dify 四件套已在本机真实跑通**。Dify 1.19 导入 DSL 后跑完 10 回合，记仇值到 100 触发结局；新会话仍能召回上一次恶作剧（PowerContext）；seekdb 账本与检索均有实测记录。模型为 DeepSeek `deepseek-flash`；Embedding 未配置，检索降级为全文模式。证据见 `evidence/screenshots/` 与 `evidence/logs/`，实测细节见 `docs/02-运行说明.md` 第 13 节。

## 目录说明

| 路径 | 内容 |
| --- | --- |
| `dify/grudge-tavern.dsl.yml` | Dify Chatflow DSL，导入即用 |
| `seed/` | 建表 SQL、道具与剧本数据、向量灌库脚本 |
| `bridge/` | 薄桥接服务（seekdb 检索 + PowerContext 记忆代理 + 状态账本） |
| `scripts/` | DSL 自检、端到端冒烟、建表执行 |
| `deploy/` | seekdb + bridge 的 docker compose |
| `docs/` | 作品设计、运行说明、验证样例、提交材料清单 |
| `evidence/` | 运行证据：`logs/` 为实测日志，截图/录屏按 `evidence/README.md` 采集 |

# 记仇酒馆 · Grudge Tavern
