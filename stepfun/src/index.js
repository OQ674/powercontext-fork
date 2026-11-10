/**
 * StepFun 迷你知识库应用 Node.js 主服务
 * 提供静态前端托管与基于 seekdb-js 的统一混合检索 REST API
 */

import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { SeekdbService } from './seekdb_service.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// 静态前端文件托管
const publicDir = path.resolve(__dirname, '../public');
app.use(express.static(publicDir));

// 初始化 SeekDB 服务
const seekdbService = new SeekdbService();

// 1. 获取系统状态
app.get('/api/status', async (req, res) => {
  try {
    const status = await seekdbService.getStatus();
    res.json({ success: true, ...status });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 2. 增量导入文档与本地向量
app.post('/api/documents', async (req, res) => {
  try {
    const { ids, documents, embeddings, metadatas } = req.body;
    if (!ids || !documents || ids.length === 0) {
      return res.status(400).json({ success: false, error: '缺少有效的 ids 或 documents 参数' });
    }
    const result = await seekdbService.addDocuments({ ids, documents, embeddings, metadatas });
    res.json(result);
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 3. seekdb 原生统一混合检索 (Full-Text + Vector KNN + RRF)
app.post('/api/search', async (req, res) => {
  try {
    const { queryText, queryEmbedding, topK, rrfK } = req.body;
    if (!queryText && (!queryEmbedding || queryEmbedding.length === 0)) {
      return res.status(400).json({ success: false, error: '查询文本与向量不能同时为空' });
    }
    const result = await seekdbService.hybridSearch({
      queryText,
      queryEmbedding,
      topK: topK || 5,
      rrfK: rrfK || 60,
    });
    res.json({ success: true, ...result });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 4. 显式触发索引刷新 (Refresh Index)
app.post('/api/refresh', async (req, res) => {
  try {
    const result = await seekdbService.refreshIndex();
    res.json({ success: true, ...result });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 5. 重置/清空知识库集合
app.post('/api/reset', async (req, res) => {
  try {
    const result = await seekdbService.reset();
    res.json({ success: true, ...result });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 6. 获取预设评测基准数据集
app.get('/api/corpus', (req, res) => {
  const corpusPath = path.resolve(publicDir, 'test_corpus.json');
  if (fs.existsSync(corpusPath)) {
    const data = JSON.parse(fs.readFileSync(corpusPath, 'utf8'));
    res.json({ success: true, data });
  } else {
    res.status(404).json({ success: false, error: '内置评测数据集不存在' });
  }
});

// 启动服务
async function startServer() {
  await seekdbService.initialize();
  app.listen(PORT, () => {
    console.log(`====================================================`);
    console.log(`[StepFun Mini Knowledge Base] 服务已就绪!`);
    console.log(`本地访问地址: http://localhost:${PORT}`);
    console.log(`SeekDB 运行模式: ${seekdbService.activeMode}`);
    console.log(`====================================================`);
  });
}

startServer().catch(err => {
  console.error('[StepFun] 服务启动失败:', err);
});
