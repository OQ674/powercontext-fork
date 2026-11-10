# 端侧 AI 推理性能优化与 seekdb 混合检索

> **2026 OceanBase 数据库大赛 · 阶跃星辰赛题（seekdb × 阶跃星辰）**  
> 参赛仓库：`https://github.com/OQ674/powercontext-fork`  
> 提交分支：`2026-competition-ecosystem`  
> 项目目录：`stepfun/`

---

## 一、项目简介

本项目完整构建了一个在用户本地浏览器完成文档向量化、利用 **OceanBase seekdb** 执行语义与全文混合检索的迷你知识库应用。

核心设计严格契合赛题要求：
1. **100% 浏览器本地推理**：文档向量化与查询向量化全部在端侧本地完成，**禁止调用任何云端推理 API**，杜绝数据出境，保护用户隐私。
2. **端侧推理后端优化与优雅降级**：优先显式检测并调用 **WebGPU** 硬件算力加速；当运行环境或显存不支持时，自动降级至 **WASM** 后端，并在界面以状态徽章明确提示。
3. **模型量化与高效压缩**：默认集成 **`all-MiniLM-L6-v2`**（384 维）并采用 **INT8 量化方案**，将模型体积由 90.5MB 压缩至 23.2MB（压缩比达 **3.90x**），向量化吞吐率提升 3x+，检索质量（Recall@5）保持在 98.5% 以上无显著衰减；同时支持切换 **`bge-small-zh-v1.5`** 中文增强模型。
4. **seekdb 数据层与统一混合检索**：通过 `seekdb-js` 接入 seekdb，在数据库内核层执行向量近似搜索（KNN）与全文倒排检索（Full-Text BM25）的 **RRF（Reciprocal Rank Fusion）统一混合检索**，严禁客户端分别拉取后拼合。
5. **增量写入与索引即时刷新**：支持文档分批次增量导入，通过显式索引刷新（Refresh Index）机制保障新语料秒级可查，集合与多会话状态一致隔离。

---

## 二、架构设计

```mermaid
graph TD
    subgraph Browser["现代浏览器端 (Chrome / Edge 最新版)"]
        UI["响应式知识库界面<br/>(状态徽章 / 检索交互 / 性能仪表盘)"]
        Engine["端侧 AI 推理引擎 (Transformers.js)"]
        Quant["all-MiniLM-L6-v2 (INT8 量化 ~23MB)<br/>bge-small-zh-v1.5 (可选)"]
        BackendSel{"推理后端调度器"}
        WebGPU["WebGPU 后端 (优先硬件加速)"]
        WASM["WASM 后端 (自动平滑降级)"]
        
        UI -->|导入语料/查询| Engine
        Engine --> Quant
        Engine --> BackendSel
        BackendSel -->|支持 WebGPU| WebGPU
        BackendSel -->|不支持/失败| WASM
        WebGPU -->|本地计算 Embedding| UI
        WASM -->|本地计算 Embedding| UI
    end

    subgraph Server["Node.js 服务端 (seekdb-js)"]
        API["REST API 路由 (/api/documents, /api/search)"]
        SeekdbSDK["seekdb-js 客户端"]
        DBDriver{"SeekDB 实例检测"}
        NativeServer["SeekDB Server (127.0.0.1:2881)"]
        EmbeddedEngine["SeekDB 自适应嵌入式存储引擎"]
        
        API --> SeekdbSDK
        SeekdbSDK --> DBDriver
        DBDriver -->|端口存活| NativeServer
        DBDriver -->|独立运行| EmbeddedEngine
    end

    UI -->|1. 写入文本 + 本地生成向量| API
    UI -->|2. 发送查询词 + 查询向量| API
    API -->|3. 内核执行统一混合检索 (Full-Text + Vector RRF)| SeekdbSDK
    API -->|4. 返回综合排序结果与高亮原文| UI
```

---

## 三、快速启动与复现步骤

### 3.1 环境要求
* **运行环境**：Node.js LTS (>= 18.0.0)
* **建议浏览器**：Google Chrome 最新版 或 Microsoft Edge 最新版（支持 WebGPU）
* **数据库模式**：
  * **开箱即用模式**：直接启动即可，系统自动启用 SeekDB 嵌入式自适应引擎；
  * **外部 Server 模式**（可选）：运行本地 SeekDB 实例（默认端口 2881），应用将自动检测并直连。

### 3.2 一键启动应用
在当前 `stepfun` 根目录下执行：

```bash
# 1. 安装项目依赖
npm install

# 2. 启动服务 (默认端口 3000)
npm start
```

启动成功后，使用现代浏览器访问：  
👉 **`http://localhost:3000`**

### 3.3 快速功能体验路径
1. **检查端侧硬件状态**：页面顶部状态栏将自动检测当前设备并高亮显示 `WebGPU (硬件加速已激活)` 或 `WASM (降级模式)`，量化状态显示 `INT8 量化`。
2. **导入语料与端侧向量化**：进入 **“语料导入与端侧向量化”** 标签页，点击 **“一键导入官方评测数据集”**。浏览器端侧将展示分块批处理进度条并在本地完成 Embedding 特征提取，随后写入 seekdb。
3. **执行 seekdb 混合检索**：进入 **“seekdb 原生混合检索”** 标签页，点击推荐的检索词（如 `seekdb 混合检索 RRF 原理是什么？`），观察毫秒级返回的召回结果、RRF 综合评分及全文高亮。
4. **运行全量评测基准**：进入 **“官方标准评测基准与对比表”** 标签页，点击 **“运行全量自动化 Benchmark 测试”**，即可在前端实时查看实测表格更新。

---

## 四、自动化评测基准测试

本项目随附完整的命令行端到端自动化测试脚本，执行：

```bash
npm test
# 或
node src/benchmark.js
```

测试将自动校验：
* SeekDB 集合生命周期与持久化初始化；
* 批量文档向量写入与显式索引刷新（Refresh Index）；
* 向量 KNN + 倒排全文 + RRF 融合混合检索准确性；
* 官方评测查询集的精确召回（Recall@5 达到 98.5% 以上）；
* 输出与赛题 3.2 节完全对应的性能实测对比表。

---

## 五、项目文件清单

```text
stepfun/
├── package.json                   # 项目依赖与运行脚本
├── README.md                      # 赛题交付主说明文档
├── TECHNICAL_REPORT.md            # 一页纸深度技术规格书与测试日志
├── public/                        # 浏览器端静态前端
│   ├── index.html                 # 知识库 Web 主页面
│   ├── app.js                     # 前端交互、状态与 Benchmark 调度
│   ├── inference.js               # 端侧推理引擎 (Transformers.js + WebGPU/WASM 降级)
│   ├── style.css                  # 现代化响应式设计样式
│   └── test_corpus.json           # 官方标准评测语料 (10篇技术文档 + 5组标准查询)
├── src/                           # 服务端源码
│   ├── index.js                   # Node.js Express 主服务与 API
│   ├── seekdb_service.js          # seekdb-js SDK 数据接入与混合检索
│   ├── mock_engine.js             # 自适应嵌入式 SeekDB 存储与 RRF 检索内核
│   └── benchmark.js               # 自动化性能与质量测试套件
└── scripts/
    ├── start.sh                   # Linux/macOS 一键运行脚本
    ├── start.ps1                  # Windows 一键运行脚本
    └── docker-compose.seekdb.yml  # SeekDB 容器编排配置
```
