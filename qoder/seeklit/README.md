# SeekLit · 科研文献混合检索库

> **2026 OceanBase 数据库大赛 · Qoder 生态赛题作品**  
> 参赛仓库：`https://github.com/OQ674/powercontext-fork`  
> 提交分支：`2026-competition-ecosystem`  
> 项目目录：`qoder/seeklit/`  
> 让学习与科研中的「文献资料难查找」不再是问题。

**线上地址**：https://seeklit-0c1mc6asy02.qoder.zone （Qoder Sites 发布，公开可访问）

## 项目简介

SeekLit 是一个面向学生与科研人员的文献知识库：把标题、作者、年份、来源、标签、摘要存入 **OceanBase seekdb**（嵌入式模式，pyseekdb SDK），用 **混合检索** 一句话找到想要的文献——

- **语义检索**（向量路）：用自然语言描述需求（如「大模型如何利用外部知识」），即使文献中没有出现这些词也能被召回；
- **关键词检索**（全文路）：ik 分词的倒排索引精确匹配术语（如「Paxos」「LSM-tree」）；
- **混合检索**（RRF 融合）：两路结果 Reciprocal Rank Fusion 融合排序，兼得语义泛化与术语精确，结果卡片上直接标注每条命中的来源（向量排名 / 全文排名）。

这是 seekdb「一库三检索」能力的直接展示：向量索引、全文索引与标量过滤（年份 / 来源 / 标签）在单引擎内完成，不需要 ES + 向量库 + 关系库三件套拼装。

## 架构

```
浏览器（Qoder Sites 发布的静态站）
   │  同源 fetch  /functions/v1/app/*
   ▼
Qoder Sites Function（Deno edge，白名单转发 + 8s 超时 + 离线降级）
   │  HTTPS（cloudflared 快速隧道）
   ▼
FastAPI 后端（WSL Ubuntu 内）
   │  pyseekdb SDK
   ▼
OceanBase seekdb（嵌入式）── ~/seeklit-data
   向量索引(IVF cosine) + ik 全文索引 + 标量元数据
```

## 目录结构

```
├── README.md              # 项目介绍/架构/seekdb 混合检索讲解/启动说明
├── web\                   # 纯静态前端（零 npm 依赖，3 个文件）
│   ├── index.html         # 单页：搜索(三模式切换)+过滤+结果(来源徽章)+管理弹窗
│   ├── style.css / app.js # 样式 + 唯一请求出口（503 BACKEND_OFFLINE → 离线横幅）
├── functions\index.ts     # Qoder Sites Function（Deno）：白名单转发 + 8s 超时 + 离线降级
├── backend\               # WSL 内运行
│   ├── main.py / db.py    # FastAPI + pyseekdb 封装（collection: 向量+全文+标量过滤）
│   ├── requirements.txt
│   └── seed\papers.csv（48 条中英文献）+ seed_import.py（幂等导入）
├── dev\                   # 本地开发入口（不进发布包）
└── scripts\               # 一键启动 / 隧道 / Secret 更新指引
```

- **数据全部存于 seekdb**：标题+摘要作为 document（自动 ONNX 向量化，无需任何 API Key），元数据作为标量字段支持过滤；
- **后端不可达时**：Function 返回稳定错误码 `BACKEND_OFFLINE`，前端展示离线横幅与本地运行指引，不白屏；
- **命中来源标注**：hybrid 模式并行执行混合/纯语义/纯全文三路查询，反查标注 `sources/vector_rank/fulltext_rank`，让混合检索「看得见」。

## 三个硬性要求的落实

| 赛题要求 | 落实方式 |
|---|---|
| 必须使用 Qoder 开发 | 全部代码在 Qoder（AI IDE）会话中生成、调试与发布 |
| 核心功能实际使用 seekdb | 检索核心 = pyseekdb 的向量 + 全文 + RRF 混合检索与标量过滤（见 `backend/db.py`），线上可实时体验 |
| 通过 Qoder Sites 发布 | 静态站 + Sites Function（`functions/index.ts`）经 prepare/publish 流程发布 |

## 本地运行（3 步）

前置：Windows 11 + WSL2（Ubuntu-24.04）+ Deno

```powershell
# 1) 首次：WSL 内建 venv 并安装依赖
wsl -d Ubuntu-24.04 -u root -- bash -c "
  apt-get install -y python3-venv &&
  python3 -m venv ~/venvs/seeklit &&
  ~/venvs/seeklit/bin/pip install -r /mnt/d/文件/文档/Oceanbase大赛/速成/Qoder/seeklit/backend/requirements.txt &&
  cd /mnt/d/文件/文档/Oceanbase大赛/速成/Qoder/seeklit/backend/seed &&
  ~/venvs/seeklit/bin/python seed_import.py"

# 2) 日常：一键启动（WSL 后端 :8001 + Deno Function :8000 + 前端 :5173）
powershell -ExecutionPolicy Bypass -File scripts\start.ps1

# 3) 如需公网访问：启动 cloudflared 快速隧道（地址重启会变，变更后按 scripts/deploy-secret.md 更新 Secret）
powershell -ExecutionPolicy Bypass -File scripts\tunnel.ps1
```

种子数据：`backend/seed/papers.csv`（48 篇中英文文献，覆盖分布式数据库 / AI·RAG / 系统方向，标注「样例」徽章）。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 探活 + 文献总数 |
| POST | `/api/search` | 三模式检索 `{query, mode: hybrid\|semantic\|keyword, n_results, filters{year_min, year_max, venue}}` |
| GET/POST/PUT/DELETE | `/api/papers...` | 文献 CRUD（写入即自动向量化） |
| POST | `/api/import` | CSV 批量导入（≤200 条/批） |
| POST | `/api/reindex` | 手动刷新索引 |

## 卸载

项目源码直接删除目录即可；WSL 环境一键清零：`wsl --unregister Ubuntu-24.04`。
