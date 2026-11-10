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
   ├─ 实时链路：/functions/v1/app/* → Sites Function → HTTPS 隧道
   │             → FastAPI → pyseekdb → OceanBase seekdb（嵌入式）
   │             向量索引(IVF cosine) + ik 全文索引 + 标量元数据
   └─ 不可达时：web/papers.csv（48 篇只读样例快照）
                 浏览器内近似检索 + 过滤，并明确标注「本地样例」
```

## 目录结构

```
├── README.md              # 项目介绍/架构/seekdb 混合检索讲解/启动说明
├── TECHNICAL_REPORT.md    # 技术报告：seekdb 使用细节、线上实测记录、已知限制
├── web\                   # 纯静态前端（零 npm 依赖）
│   ├── index.html         # 单页：搜索(三模式切换)+过滤+结果(来源徽章)+管理弹窗
│   ├── style.css / app.js # 实时请求、4.5s 超时、状态切换与只读样例检索
│   └── papers.csv         # 与 seekdb 种子数据一致的 48 篇静态快照
├── functions\index.ts     # Qoder Sites Function（Deno）：白名单转发 + 8s 超时 + 离线降级
├── backend\               # WSL 内运行
│   ├── main.py / db.py    # FastAPI + pyseekdb 封装（collection: 向量+全文+标量过滤）
│   ├── requirements.txt
│   └── seed\papers.csv（48 条中英文献）+ seed_import.py（幂等导入）
├── dev\                   # 本地 Function 与离线回归测试
└── scripts\               # 一键启动 / 隧道 / Secret 更新指引（不会自动下载工具）
```

- **数据全部存于 seekdb**：标题+摘要+标签作为 document（自动 ONNX 向量化，无需任何 API Key；标签并入是因为 ik 全文索引只覆盖 document 列），其余字段作为标量元数据支持过滤；
- **后端不可达时**：Function 返回稳定错误码 `BACKEND_OFFLINE`；前端自动载入随站点发布的 48 篇只读快照，支持浏览、三种近似排序、年份/来源/标签过滤，并明确标注「本地样例」。新增、删除和导入会被禁用，浏览器结果不会冒充 seekdb；
- **命中来源标注**：hybrid 模式并行执行混合/纯语义/纯全文三路查询，反查标注 `sources/vector_rank/fulltext_rank`，让混合检索「看得见」。
- **过滤一致性**：混合检索的全文路与 KNN 路使用同一个 `where`；标签过滤先扩大候选集、再按标签成员精确筛选，避免 RRF 混回范围外结果或 top-k 后过滤导致漏召回。

## 三个硬性要求的落实

| 赛题要求 | 落实方式 |
|---|---|
| 必须使用 Qoder 开发 | 项目由 Qoder（AI IDE）会话完成需求拆解、主体编码、联调与首次发布；会话产物和站点描述文件随项目保留 |
| 核心功能实际使用 seekdb | 实时模式的检索核心 = pyseekdb 的向量 + 全文 + RRF 混合检索与标量过滤（见 `backend/db.py`）；样例降级与实时结果在界面上严格区分 |
| 通过 Qoder Sites 发布 | 静态站 + Sites Function（`functions/index.ts`）经 Qoder Sites prepare/publish 流程发布 |

## 本地运行（3 步）

前置：Windows 11 + WSL2（Ubuntu-24.04）+ Deno。脚本只使用本机已有环境，不会静默安装依赖或下载 cloudflared。

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
| POST | `/api/search` | 三模式检索 `{query, mode: hybrid\|semantic\|keyword, n_results, filters{year_min, year_max, venue, tags}}` |
| GET/POST/PUT/DELETE | `/api/papers...` | 文献 CRUD（写入即自动向量化） |
| POST | `/api/import` | CSV 批量导入（≤200 条/批） |
| POST | `/api/reindex` | 手动刷新索引 |

## 验证

```powershell
node --check web\app.js
node dev\offline_smoke_test.js
python backend\seed\check_csv.py
deno check functions\index.ts
deno check dev\function-local.ts
```

`offline_smoke_test.js` 会模拟 Function 返回 503，验证 48 篇快照、样例标识、检索和组合过滤；真实 seekdb 回归还应确认年份过滤结果全部落在范围内，以及标签过滤能召回对应文献。
