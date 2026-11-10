/**
 * StepFun 迷你知识库应用前端交互主逻辑 (app.js)
 * 编排端侧向量化推理与 seekdb 统一混合检索
 */

import {
  initInferenceEngine,
  encodeText,
  encodeBatch,
  InferenceState,
  MODEL_SPECS,
} from './inference.js';

// DOM 元素引用
const backendBadge = document.getElementById('backendBadge');
const quantBadge = document.getElementById('quantBadge');
const seekdbBadge = document.getElementById('seekdbBadge');

const modelSelect = document.getElementById('modelSelect');
const quantSelect = document.getElementById('quantSelect');
const backendSelect = document.getElementById('backendSelect');
const btnInitModel = document.getElementById('btnInitModel');

const metricBackend = document.getElementById('metricBackend');
const metricBackendSub = document.getElementById('metricBackendSub');
const metricModelSize = document.getElementById('metricModelSize');
const metricRatio = document.getElementById('metricRatio');
const metricThroughput = document.getElementById('metricThroughput');
const metricEmbedTime = document.getElementById('metricEmbedTime');
const metricDbLatency = document.getElementById('metricDbLatency');
const metricE2eLatency = document.getElementById('metricE2eLatency');

const searchInput = document.getElementById('searchInput');
const btnSearch = document.getElementById('btnSearch');
const topKSelect = document.getElementById('topKSelect');
const rrfKInput = document.getElementById('rrfKInput');
const resultsCount = document.getElementById('resultsCount');
const latencyBreakdown = document.getElementById('latencyBreakdown');
const resultsList = document.getElementById('resultsList');

const btnLoadSampleCorpus = document.getElementById('btnLoadSampleCorpus');
const btnRefreshIndex = document.getElementById('btnRefreshIndex');
const btnClearKB = document.getElementById('btnClearKB');
const btnImportCustom = document.getElementById('btnImportCustom');
const customDocTitle = document.getElementById('customDocTitle');
const customDocContent = document.getElementById('customDocContent');

const importProgressBox = document.getElementById('importProgressBox');
const progressTitle = document.getElementById('progressTitle');
const progressPercent = document.getElementById('progressPercent');
const progressBarFill = document.getElementById('progressBarFill');
const progressDetails = document.getElementById('progressDetails');

const kbDocCount = document.getElementById('kbDocCount');
const kbMode = document.getElementById('kbMode');

const btnRunBenchmark = document.getElementById('btnRunBenchmark');
const benchmarkStatusText = document.getElementById('benchmarkStatusText');

// 标签页切换逻辑
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const targetId = btn.getAttribute('data-tab');
    document.getElementById(targetId)?.classList.add('active');
  });
});

// 快速查询推荐 Chip 绑定
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    searchInput.value = chip.getAttribute('data-query');
    executeSearch();
  });
});

/**
 * 刷新 UI 状态与指标面板
 */
function updateUIMetrics() {
  const model = modelSelect.value;
  const isQuant = quantSelect.value === 'int8';
  const spec = MODEL_SPECS[model] || { fp32SizeMB: 90, int8SizeMB: 23, compressionRatio: 3.9 };

  // 1. 活跃推理后端 Badge
  const backend = InferenceState.activeBackend;
  if (backend === 'webgpu') {
    backendBadge.className = 'badge badge-success';
    backendBadge.innerHTML = '<span class="dot"></span> WebGPU (硬件加速已激活)';
    metricBackend.textContent = 'WebGPU';
    metricBackendSub.textContent = 'Chrome/Edge 硬件渲染加速';
  } else if (backend === 'wasm') {
    backendBadge.className = 'badge badge-warning';
    backendBadge.innerHTML = '<span class="dot"></span> WASM (已降级至 CPU 运行)';
    metricBackend.textContent = 'WASM';
    metricBackendSub.textContent = 'WebAssembly 降级兼容模式';
  } else {
    backendBadge.className = 'badge badge-info';
    backendBadge.innerHTML = '<span class="dot"></span> 后端加载中...';
    metricBackend.textContent = '--';
  }

  // 2. 模型量化 Badge 与体积
  if (isQuant) {
    quantBadge.className = 'badge badge-purple';
    quantBadge.textContent = 'INT8 量化方案';
    metricModelSize.textContent = `${spec.int8SizeMB} MB`;
    metricRatio.textContent = `压缩比: ${spec.compressionRatio}x (原 ${spec.fp32SizeMB}MB)`;
  } else {
    quantBadge.className = 'badge badge-secondary';
    quantBadge.textContent = 'FP32 原始基线';
    metricModelSize.textContent = `${spec.fp32SizeMB} MB`;
    metricRatio.textContent = `基线未压缩 (1.00x)`;
  }
}

/**
 * 初始化或重载端侧推理引擎
 */
async function setupEngine() {
  btnInitModel.disabled = true;
  btnInitModel.textContent = '正在加载端侧模型...';

  try {
    const model = modelSelect.value;
    const isQuant = quantSelect.value === 'int8';
    const backendPref = backendSelect.value;

    await initInferenceEngine({
      modelName: model,
      quantized: isQuant,
      preferBackend: backendPref,
      onProgress: (p) => {
        if (p.status === 'progress') {
          btnInitModel.textContent = `加载中: ${Math.round(p.progress || 0)}%`;
        }
      },
    });

    updateUIMetrics();
    btnInitModel.textContent = '重新加载/热切换';
  } catch (err) {
    console.error('[App] 模型初始化失败:', err);
    alert(`模型加载失败: ${err.message}`);
    btnInitModel.textContent = '加载失败, 点击重试';
  } finally {
    btnInitModel.disabled = false;
  }
}

/**
 * 查询 SeekDB 服务端运行状态
 */
async function fetchSeekdbStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.success) {
      seekdbBadge.className = 'badge badge-success';
      seekdbBadge.textContent = `SeekDB: 在线 (${data.mode === 'seekdb_server' ? 'Server' : 'Embedded'})`;
      kbDocCount.textContent = data.documentCount || 0;
      kbMode.textContent = data.mode === 'seekdb_server' ? 'Server (127.0.0.1:2881)' : '自适应嵌入式 (Local)';
    } else {
      seekdbBadge.className = 'badge badge-warning';
      seekdbBadge.textContent = 'SeekDB: 状态异常';
    }
  } catch (err) {
    seekdbBadge.className = 'badge badge-warning';
    seekdbBadge.textContent = 'SeekDB: 本地模拟就绪';
  }
}

/**
 * 执行统一混合检索 (Hybrid Search)
 * 严格流程：浏览器本地计算 query 向量 -> 发送至 seekdb -> seekdb 内核执行 Full-Text + Vector RRF 融合
 */
async function executeSearch() {
  const query = searchInput.value.trim();
  if (!query) {
    alert('请输入有效的查询文本');
    return;
  }

  const e2eStartTime = performance.now();
  btnSearch.disabled = true;
  btnSearch.textContent = '正在本地向量化...';

  try {
    // 阶段 1: 浏览器本地端侧向量化
    const embedStart = performance.now();
    const embedResult = await encodeText(query);
    const embedDuration = Math.round(performance.now() - embedStart);

    btnSearch.textContent = 'seekdb 正在执行混合检索...';

    // 阶段 2: seekdb 执行统一混合检索
    const dbStart = performance.now();
    const topK = parseInt(topKSelect.value, 10);
    const rrfK = parseInt(rrfKInput.value, 10);

    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        queryText: query,
        queryEmbedding: embedResult.embedding,
        topK,
        rrfK,
      }),
    });
    const data = await res.json();
    const dbDuration = Math.round(performance.now() - dbStart);
    const e2eDuration = Math.round(performance.now() - e2eStartTime);

    // 阶段 3: 更新性能监控卡片
    metricDbLatency.textContent = `${dbDuration} ms`;
    metricE2eLatency.textContent = `${e2eDuration} ms`;

    latencyBreakdown.innerHTML = `
      <span class="chip">端侧向量化: ${embedDuration}ms</span>
      <span class="chip">seekdb 混合检索: ${dbDuration}ms</span>
      <span class="chip" style="color: var(--accent-green); font-weight:600">总延迟: ${e2eDuration}ms</span>
    `;

    // 阶段 4: 渲染检索结果列表
    renderSearchResults(data.results || [], query);
  } catch (err) {
    console.error('[Search] 检索失败:', err);
    alert(`检索执行失败: ${err.message}`);
  } finally {
    btnSearch.disabled = false;
    btnSearch.textContent = '本地向量化并检索';
  }
}

/**
 * 渲染结果卡片
 */
function renderSearchResults(results, query) {
  resultsCount.textContent = results.length;
  if (!results || results.length === 0) {
    resultsList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <p>未找到匹配的相关文档，请先在“语料导入”标签页中导入文档或重新检索。</p>
      </div>
    `;
    return;
  }

  const queryTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 0);

  resultsList.innerHTML = results.map((item, idx) => {
    let highlightedText = item.text || '';
    for (const term of queryTerms) {
      const regex = new RegExp(`(${term})`, 'gi');
      highlightedText = highlightedText.replace(regex, '<strong>$1</strong>');
    }

    const rrfScoreFormatted = (item.rrfScore || 0).toFixed(4);
    const vecScoreFormatted = item.vectorScore !== undefined ? (item.vectorScore).toFixed(3) : '--';
    const ftScoreFormatted = item.fulltextScore !== undefined ? (item.fulltextScore).toFixed(2) : '--';

    return `
      <div class="result-card">
        <div class="result-card-header">
          <span class="result-title">#${idx + 1} ${item.metadata?.title || item.id}</span>
          <div class="result-scores">
            <span class="score-badge rrf" title="Reciprocal Rank Fusion 综合得分">RRF 得分: ${rrfScoreFormatted}</span>
            <span class="score-badge" title="端侧向量余弦相似度">向量相似度: ${vecScoreFormatted}</span>
            <span class="score-badge" title="倒排全文检索得分">全文 BM25: ${ftScoreFormatted}</span>
          </div>
        </div>
        <div class="result-body">${highlightedText}</div>
      </div>
    `;
  }).join('');
}

/**
 * 导入预设官方基准评测语料 (10篇核心技术文档)
 */
async function loadSampleCorpus() {
  btnLoadSampleCorpus.disabled = true;
  importProgressBox.classList.remove('hidden');
  progressTitle.textContent = '正在获取官方评测数据集...';
  progressPercent.textContent = '0%';
  progressBarFill.style.width = '0%';

  try {
    const res = await fetch('/api/corpus');
    const json = await res.json();
    if (!json.success || !json.data?.documents) {
      throw new Error('未获取到预设评测文档');
    }

    const docs = json.data.documents;
    const texts = docs.map(d => d.text);
    const ids = docs.map(d => d.id);
    const metadatas = docs.map(d => ({ title: d.title, category: d.category, tags: d.tags }));

    progressTitle.textContent = `端侧正在批量向量化 (共 ${docs.length} 篇)...`;

    // 浏览器端批量向量化
    const batchRes = await encodeBatch(texts, {
      batchSize: 2,
      onProgress: (p) => {
        progressPercent.textContent = `${p.percentage}%`;
        progressBarFill.style.width = `${p.percentage}%`;
        progressDetails.textContent = `已本地向量化: ${p.processed} / ${p.total} 篇`;
      },
    });

    metricThroughput.textContent = `${batchRes.throughputDocsPerSec} docs/s`;
    metricEmbedTime.textContent = `批量耗时: ${Math.round(batchRes.totalDurationMs)} ms`;

    // 写入 seekdb
    progressTitle.textContent = '正在写入 seekdb 并刷新索引...';
    const writeRes = await fetch('/api/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ids,
        documents: texts,
        embeddings: batchRes.embeddings,
        metadatas,
      }),
    });
    const writeData = await writeRes.json();

    if (writeData.success) {
      alert(`导入成功! 已在本地完成 ${docs.length} 篇文档向量化并写入 seekdb。`);
      await fetchSeekdbStatus();
    } else {
      throw new Error(writeData.error || '写入失败');
    }
  } catch (err) {
    console.error('[Corpus] 导入失败:', err);
    alert(`语料导入失败: ${err.message}`);
  } finally {
    btnLoadSampleCorpus.disabled = false;
    setTimeout(() => {
      importProgressBox.classList.add('hidden');
    }, 2000);
  }
}

/**
 * 导入自定义单篇文档
 */
async function importCustomDoc() {
  const title = customDocTitle.value.trim() || '未命名文档';
  const content = customDocContent.value.trim();
  if (!content) {
    alert('请输入文档正文内容');
    return;
  }

  btnImportCustom.disabled = true;
  btnImportCustom.textContent = '正在本地向量化...';

  try {
    const embedRes = await encodeText(content);
    const docId = `custom_${Date.now()}`;

    btnImportCustom.textContent = '正在写入 seekdb...';
    const res = await fetch('/api/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ids: [docId],
        documents: [content],
        embeddings: [embedRes.embedding],
        metadatas: [{ title, custom: true }],
      }),
    });

    const data = await res.json();
    if (data.success) {
      alert(`文档《${title}》已成功向量化并写入 seekdb!`);
      customDocTitle.value = '';
      customDocContent.value = '';
      await fetchSeekdbStatus();
    }
  } catch (err) {
    console.error('[CustomImport] 失败:', err);
    alert(`写入失败: ${err.message}`);
  } finally {
    btnImportCustom.disabled = false;
    btnImportCustom.textContent = '本地向量化并写入 seekdb';
  }
}

/**
 * 显式触发索引刷新
 */
async function triggerRefresh() {
  btnRefreshIndex.disabled = true;
  try {
    const res = await fetch('/api/refresh', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      alert('seekdb 索引刷新完成! 新增文档已全部可查。');
      await fetchSeekdbStatus();
    }
  } catch (err) {
    alert(`索引刷新失败: ${err.message}`);
  } finally {
    btnRefreshIndex.disabled = false;
  }
}

/**
 * 清空知识库
 */
async function clearKB() {
  if (!confirm('确定要清空当前 seekdb 知识库集合吗？')) return;
  btnClearKB.disabled = true;
  try {
    const res = await fetch('/api/reset', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      alert('知识库已清空');
      renderSearchResults([], '');
      await fetchSeekdbStatus();
    }
  } catch (err) {
    alert(`清空失败: ${err.message}`);
  } finally {
    btnClearKB.disabled = false;
  }
}

/**
 * 运行全量标准基准自动化测试 (Tab 3)
 */
async function runFullBenchmark() {
  btnRunBenchmark.disabled = true;
  benchmarkStatusText.textContent = '正在执行全量 Benchmark 实测中...';

  try {
    // 确保有文档
    const statusRes = await fetch('/api/status');
    const statusData = await statusRes.json();
    if (!statusData.documentCount || statusData.documentCount === 0) {
      benchmarkStatusText.textContent = '检测到知识库为空，正在自动导入基准文档...';
      await loadSampleCorpus();
    }

    // 获取测试查询集
    const corpusRes = await fetch('/api/corpus');
    const corpusJson = await corpusRes.json();
    const benchmarkQueries = corpusJson.data?.benchmark_queries || [];

    // 执行 INT8 实测
    benchmarkStatusText.textContent = '正在实测当前配置下的查询延迟与 Recall@5 指标...';
    let totalE2e = 0;
    let totalDb = 0;
    let totalRecall = 0;

    for (const bq of benchmarkQueries) {
      const qStart = performance.now();
      const embed = await encodeText(bq.query_text);
      const dbStart = performance.now();
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          queryText: bq.query_text,
          queryEmbedding: embed.embedding,
          topK: 5,
        }),
      });
      const data = await res.json();
      const dbLat = performance.now() - dbStart;
      const e2eLat = performance.now() - qStart;

      totalDb += dbLat;
      totalE2e += e2eLat;

      // 评估 Recall@5: 期望 doc 是否命中
      const returnedIds = (data.results || []).map(r => r.id);
      const hitCount = bq.expected_doc_ids.filter(id => returnedIds.includes(id)).length;
      totalRecall += hitCount / bq.expected_doc_ids.length;
    }

    const avgE2e = (totalE2e / benchmarkQueries.length).toFixed(1);
    const avgDb = (totalDb / benchmarkQueries.length).toFixed(1);
    const avgRecall = ((totalRecall / benchmarkQueries.length) * 100).toFixed(1);

    // 动态刷新当前运行环境对应的表格行
    const isWebGPU = InferenceState.activeBackend === 'webgpu';
    const targetRowId = isWebGPU ? 'rowInt8WebGPU' : 'rowInt8WASM';
    const row = document.getElementById(targetRowId);
    if (row) {
      row.querySelector('[data-field="dbLatency"]').textContent = `${avgDb} ms`;
      row.querySelector('[data-field="e2eLatency"]').textContent = `${avgE2e} ms`;
      row.querySelector('[data-field="recall"]').textContent = `${avgRecall}% (实测稳定)`;
    }

    benchmarkStatusText.textContent = `实测完成! 平均端到端延迟: ${avgE2e}ms, seekdb延迟: ${avgDb}ms, Recall@5: ${avgRecall}%`;
  } catch (err) {
    console.error('[Benchmark] 测试异常:', err);
    benchmarkStatusText.textContent = `评测失败: ${err.message}`;
  } finally {
    btnRunBenchmark.disabled = false;
  }
}

// 事件监听绑定
btnInitModel.addEventListener('click', setupEngine);
btnSearch.addEventListener('click', executeSearch);
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') executeSearch();
});
btnLoadSampleCorpus.addEventListener('click', loadSampleCorpus);
btnImportCustom.addEventListener('click', importCustomDoc);
btnRefreshIndex.addEventListener('click', triggerRefresh);
btnClearKB.addEventListener('click', clearKB);
btnRunBenchmark.addEventListener('click', runFullBenchmark);

// 页面初始化自启
window.addEventListener('DOMContentLoaded', async () => {
  updateUIMetrics();
  await fetchSeekdbStatus();
  // 静默初始化端侧模型
  setupEngine();
});
