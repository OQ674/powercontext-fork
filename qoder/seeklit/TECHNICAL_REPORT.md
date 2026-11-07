# SeekLit 技术报告

> 2026 OceanBase 数据库大赛 · Qoder 生态赛题
> 参赛仓库：`https://github.com/OQ674/powercontext-fork` · 提交分支：`2026-competition-ecosystem` · 项目目录：`qoder/seeklit/`
> 线上地址：https://seeklit-0c1mc6asy02.qoder.zone

## 一、赛题要求对照

| 硬性要求 | 落实情况 | 可验证位置 |
|---|---|---|
| 使用 Qoder 开发 | 项目由 Qoder Desktop 会话完成需求拆解、主体编码、联调与首次发布；网站通过 Qoder Sites 工具链（prepare → publish）发布，并注册了设计工作台 | 线上站点页脚 Qoder 水印、`.SeekLit.qoder.site` 描述文件 |
| 核心功能实际使用 seekdb | 三种检索模式全部由 pyseekdb 在嵌入式 seekdb 内执行，没有任何应用层拼装的召回逻辑 | `backend/db.py` 的 `search_semantic` / `search_keyword` / `search_hybrid` |
| 通过 Qoder Sites 发布 | 静态前端 + Sites Function（Deno edge）已发布为公开站点，评委可直接在线体验 | 线上地址，`/functions/v1/app/*` |

## 二、seekdb 的使用细节

数据模型（collection `papers`，database `seeklit`，嵌入式数据目录 `~/seeklit-data`）：

- `document` = `标题\n摘要\n标签` —— 同时作为向量输入与全文索引列（标签并入是必要的：seekdb 的 FULLTEXT 索引只覆盖 `document` 单列，而多数中文检索词只出现在标签里）；
- `metadata` = `title / authors / year / venue / tags_csv / language / is_sample` —— 支撑标量过滤；
- `id` = 语义化主键（`db001`…），保证幂等 upsert。

四类能力在一套引擎内完成，这正是 seekdb「一库三检索」的价值主张（不需要 ES + 向量库 + 关系库三件套）：

1. **向量检索**：`col().query(query_texts=[q], n_results=k, where=...)`，向量化由 pyseekdb 内置的本地 ONNX 模型 `all-MiniLM-L6-v2`（384 维）完成，**不依赖任何外部 API Key**；
2. **全文检索**：`hybrid_search(query={"where_document": {"$contains": q}, ...})`，走 seekdb 的 FULLTEXT 索引；
3. **RRF 融合**：`rank={"rrf": {}}`，融合在数据库内核执行，应用层不做二次拼合；
4. **标量过滤**：`where` 组装 `year` 的 `$gte/$lte`、`venue` 的 `$eq` 与 `$and` 组合，全文路与 KNN 路接收同一过滤条件，避免未过滤的向量结果经 RRF 混回；标签因以分号存于单列，先扩大至最多 `k×5` 个候选，再按标签成员精确匹配并截取 top-k，兼顾准确性与召回。

写入语义与工程细节：

- **更新 = 删除 + upsert**：`PUT /api/papers/{id}` 先 delete 再 upsert，确保摘要变化后向量重新计算，而不是残留旧向量；
- **索引刷新**：批量导入后调用 `col().refresh_index()`，并暴露 `POST /api/reindex`，保证新写入语料秒级可查；
- **连接自愈**：内嵌 seekdb 的 MySQL 连接在长空闲后会报 `2006 Server has gone away`，`db.py` 用 `_run()` 包裹全部操作，识别该类错误后重建 client 并重试一次，线上演示因此不会因为夜间空闲而挂掉。

## 三、架构与请求链

```
浏览器（Qoder Sites 静态站）
  ├─ 实时：/functions/v1/app/* → Sites Function（Deno edge）
  │        → https://*.trycloudflare.com → FastAPI :8001
  │        → pyseekdb → OceanBase seekdb（嵌入式）
  └─ 降级：web/papers.csv → 浏览器内只读近似检索与过滤
```

Function 层的设计取舍：

- **白名单转发**而不是自由透传，避免公网隧道被裸扫；只允许 `/health /search /papers /import /reindex` 等固定子路径；
- **路径归一化**：Sites 边缘会把函数名改写为 `/app-<rev>/...` 这类带部署后缀的前缀，`handler` 逐段剥掉 `functions / v1 / app-*` 前缀后再匹配白名单，因此同一份代码在本地 Deno、边缘改写前缀、改写后前缀三种形态下行为一致；
- **降级而非白屏**：后端不可达时返回稳定错误码 `503 {code:"BACKEND_OFFLINE"}`。前端请求设 4.5 秒超时，失败后自动切到随站点发布的 48 篇只读快照；状态条、横幅和结果徽章均明确写出「本地样例」，写操作被禁用，因此不会把浏览器近似排序冒充 seekdb。

## 四、实测验证记录

下表前半部分是首次发布后由 Qoder 会话对**线上实时链路**执行的历史实测；后半部分是本次加固后的本地自动化与真实 seekdb 回归。快速隧道不是固定服务，当前是否在线应以站点状态条为准。

| 场景 | 输入 | 实际结果 |
|---|---|---|
| 探活 | `GET /functions/v1/app/health` | `{"status":"ok","papers":48}` |
| 中文关键词召回 | 关键词「缓存」 | 4 条命中，#1 分布式缓存架构（全文#1） |
| 中文术语召回 | 关键词「分布式事务」 | 5 条命中：TiDB、HTAP 综述、ARIES… |
| 混合检索双路命中 | 混合「大模型如何利用外部知识」 | **#1 检索增强生成技术综述，sources = 向量 + 全文**（标题即命中词，语义路也给到前列） |
| 混合检索双路命中 | 混合「分布式共识 Paxos 协议」 | #1 分布式缓存（向量#1 + 全文#3）、#3 OceanBase（向量#14 + **全文#1**） |
| 英文术语 | 关键词「Paxos」/「consistent hashing」 | 3 条 / 2 条命中 |
| 英文语义检索 | 语义「how large language models use external knowledge」 | #1 Language Models are Few-Shot Learners、#2 Retrieval-Augmented Generation |
| 标量过滤 | `filters:{year_min:2020, tags:["向量数据库"]}` | 命中 0 条，与标签字典中不存在该标签一致；改用 `向量检索` 有结果 |
| 离线降级 | 隧道存活但源站已停（cloudflared 返回 502 HTML） | Function 统一改写为 `503 {code:"BACKEND_OFFLINE"}`，前端显示离线横幅而非报错 |
| 写入即可查 | 新增/修改/删除文献后立刻检索 | 结果与排名即时更新（PUT 走 delete+upsert 重算向量） |
| 线上页面实机 | 浏览器打开站点、输入「分布式共识 Paxos 协议」点检索 | 8 条结果卡片，均带 向量#n / 全文#n 徽章与「样例」标记 |
| 当前线上链路检查 | `GET /functions/v1/app/health` | 快速隧道已失效，Function 返回 503；页面仍可打开，发布新版后会自动进入只读样例模式 |
| 离线自动回归 | 模拟后端 503，查询「大模型如何利用外部知识」，叠加标签与年份过滤 | 载入 48 篇快照，首位命中对应论文；样例标识、缓存查询、组合过滤全部通过 |
| 真实 seekdb 年份过滤 | 混合检索 + `year_min:2020` | 返回结果年份全部 ≥ 2020，确认全文与 KNN 两路过滤一致 |
| 真实 seekdb 标签过滤 | 查询并限定 `RAG` | 返回 `ai005/ai011/ai013/ai004` 等真实标签成员，扩大候选后精确过滤通过 |
| 种子数据检查 | `backend/seed/check_csv.py` | 10 列、48 条、0 个问题；静态快照与种子 CSV 的 SHA-256 一致 |

## 五、复现步骤

前置：Windows 11 + WSL2（Ubuntu-24.04）+ Deno。仓库脚本不会自动安装依赖或下载 cloudflared；首次安装命令需要使用者自行确认网络与环境。

```powershell
# 1) 首次：WSL 内建 venv、装依赖、导入 48 条种子数据
wsl -d Ubuntu-24.04 -u root -- bash -c "
  python3 -m venv ~/venvs/seeklit &&
  ~/venvs/seeklit/bin/pip install -r backend/requirements.txt &&
  cd backend/seed && ~/venvs/seeklit/bin/python seed_import.py"

# 2) 日常：一键启动（WSL 后端 :8001 + Deno Function :8000 + 前端 :5173）
powershell -ExecutionPolicy Bypass -File scripts\start.ps1

# 3) 需要公网演示时：起 cloudflared 快速隧道，并把地址同步给 Function
powershell -ExecutionPolicy Bypass -File scripts\tunnel.ps1
```

隧道地址每次重启都会变化，两种生效方式（见 `scripts/deploy-secret.md`）：Sites Secret `SEEKLIT_BACKEND_URL`，或直接改 `functions/index.ts` 里的 `DEFAULT_BACKEND_URL` 后重新发布，约 60 秒。

### 自动化检查

```powershell
node --check web\app.js
node dev\offline_smoke_test.js
python backend\seed\check_csv.py
deno check functions\index.ts
deno check dev\function-local.ts
```

## 六、已知限制

- **实时写入与真实 seekdb 排序依赖隧道存活**：cloudflared 快速隧道无固定域名；隧道不可达时，已发布站点仍可浏览和检索 48 篇只读样例，但不会提供写入，也不会将近似排序标为 seekdb 结果。按第五节启动实时链路后可现场复现完整能力。
- **向量化模型的多语言边界**：内置 `all-MiniLM-L6-v2` 对英文语义判别更稳；中文概念句的语义路排名偏弱，本项目用「标签并入索引文本 + RRF 融合」补偿，实测中文查询已能稳定命中正确文献（见第四节），但极口语化的长句仍建议同时用关键词模式收口。
- **排错经验（值得记录）**：在 Windows 侧用 curl 直接发含中文的 JSON body 会被本地代码页改写编码，FastAPI 返回 422 解析错误，表面上像「检索无结果」。验证中文召回必须用 UTF-8 正确的客户端（浏览器、或按 UTF-8 编码 body 的脚本），否则会误判 seekdb 的全文路失效。
- **种子数据为样例**：48 条文献为演示构造的元数据（前端有「样例」徽章），不代表真实文献库规模。
