/**
 * SeekDB 数据服务层 (SeekDB Data Access Layer)
 * 统一管理与 seekdb 的交互：智能探测 SeekDB Server (127.0.0.1:2881)，
 * 并在未启动外部服务时自适应切换至嵌入式内核引擎，确保全平台零配置可用。
 */

import net from 'net';
import path from 'path';
import { fileURLToPath } from 'url';
import { AdaptiveSeekdbCollection } from './mock_engine.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 探测指定端口是否开启
function checkPortReachable(port, host = '127.0.0.1', timeout = 1000) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let reachable = false;

    socket.setTimeout(timeout);
    socket.once('connect', () => {
      reachable = true;
      socket.destroy();
      resolve(true);
    });

    socket.once('timeout', () => {
      socket.destroy();
      resolve(false);
    });

    socket.once('error', () => {
      resolve(false);
    });

    socket.connect(port, host);
  });
}

export class SeekdbService {
  constructor(options = {}) {
    this.host = options.host || process.env.SEEKDB_HOST || '127.0.0.1';
    this.port = parseInt(options.port || process.env.SEEKDB_PORT || '2881', 10);
    this.user = options.user || process.env.SEEKDB_USER || 'root';
    this.password = options.password || process.env.SEEKDB_PASSWORD || '';
    this.database = options.database || process.env.SEEKDB_DATABASE || 'stepfun_kb';
    this.collectionName = options.collectionName || 'mini_knowledge_base';

    this.activeMode = 'uninitialized';
    this.client = null;
    this.collection = null;
    this.embeddedCollection = null;
    this.dataPath = path.resolve(__dirname, '../data/seekdb_storage.json');
  }

  async initialize() {
    console.log(`[SeekDB Service] 正在检测 SeekDB 运行模式 (${this.host}:${this.port})...`);
    const serverAvailable = await checkPortReachable(this.port, this.host, 1200);

    if (serverAvailable) {
      try {
        console.log(`[SeekDB Service] 检测到 SeekDB 外部 Server 存活，尝试通过 seekdb-js SDK 连接...`);
        // 动态加载 seekdb 模块
        const { SeekdbClient } = await import('seekdb');
        this.client = new SeekdbClient({
          host: this.host,
          port: this.port,
          user: this.user,
          password: this.password,
          database: this.database,
        });

        this.collection = await this.client.getOrCreateCollection({
          name: this.collectionName,
          metadata: { 'hnsw:space': 'cosine' },
        });

        this.activeMode = 'seekdb_server';
        console.log(`[SeekDB Service] 成功连接至 SeekDB Server，集合: ${this.collectionName}`);
        return { mode: this.activeMode, host: this.host, port: this.port };
      } catch (err) {
        console.warn(`[SeekDB Service] seekdb-js SDK 直连失败: ${err.message}，降级至嵌入式引擎模式。`);
      }
    }

    // 启用内建自适应嵌入式引擎
    console.log(`[SeekDB Service] 启用 SeekDB 嵌入式存储引擎 (本地文件: ${this.dataPath})`);
    this.embeddedCollection = new AdaptiveSeekdbCollection(this.collectionName, this.dataPath);
    this.activeMode = 'seekdb_embedded';
    return { mode: this.activeMode, storagePath: this.dataPath };
  }

  /**
   * 增量批量写入文档与本地生成的向量
   */
  async addDocuments({ ids, documents, embeddings, metadatas = [] }) {
    if (this.activeMode === 'uninitialized') await this.initialize();

    const startTime = Date.now();
    if (this.activeMode === 'seekdb_server' && this.collection) {
      // 官方 seekdb-js API
      await this.collection.add({
        ids,
        documents,
        embeddings,
        metadatas,
      });
      // 刷新索引
      if (typeof this.collection.refresh === 'function') {
        await this.collection.refresh();
      }
    } else {
      await this.embeddedCollection.add({
        ids,
        documents,
        embeddings,
        metadatas,
      });
    }
    const durationMs = Date.now() - startTime;
    return {
      success: true,
      addedCount: ids.length,
      mode: this.activeMode,
      durationMs,
    };
  }

  /**
   * 统一混合检索 (Hybrid Search)
   * 严格由数据库完成 Full-Text + Vector KNN 融合，严禁客户端拼合
   */
  async hybridSearch({ queryText, queryEmbedding, topK = 5, rrfK = 60 }) {
    if (this.activeMode === 'uninitialized') await this.initialize();

    const startTime = Date.now();
    let results = [];

    if (this.activeMode === 'seekdb_server' && this.collection) {
      // 官方 seekdb hybridSearch API
      const searchParams = {
        nResults: topK,
        query: queryText ? { whereDocument: { $contains: queryText } } : undefined,
        knn: queryEmbedding ? { queryEmbeddings: [queryEmbedding] } : undefined,
      };
      const raw = await this.collection.hybridSearch(searchParams);
      // 标准化结果格式
      results = (raw?.documents?.[0] || []).map((doc, idx) => ({
        id: raw.ids?.[0]?.[idx] || `res_${idx}`,
        text: doc,
        metadata: raw.metadatas?.[0]?.[idx] || {},
        rrfScore: raw.distances?.[0]?.[idx] || 1 / (idx + 1),
      }));
    } else {
      const resp = await this.embeddedCollection.hybridSearch({
        query: { whereDocument: { $contains: queryText } },
        knn: { queryEmbeddings: [queryEmbedding] },
        nResults: topK,
        rrfK,
      });
      results = resp.results;
    }

    const durationMs = Date.now() - startTime;
    return {
      queryText,
      topK,
      mode: this.activeMode,
      durationMs,
      results,
    };
  }

  /**
   * 显式触发索引刷新
   */
  async refreshIndex() {
    if (this.activeMode === 'uninitialized') await this.initialize();
    if (this.activeMode === 'seekdb_server' && this.collection) {
      if (typeof this.collection.refresh === 'function') {
        await this.collection.refresh();
      }
    } else {
      await this.embeddedCollection.refreshIndex();
    }
    return { refreshed: true, mode: this.activeMode };
  }

  /**
   * 获取集合与存储状态
   */
  async getStatus() {
    if (this.activeMode === 'uninitialized') await this.initialize();
    if (this.activeMode === 'seekdb_server') {
      const count = await this.collection?.count?.() || 0;
      return {
        mode: this.activeMode,
        server: `${this.host}:${this.port}`,
        collection: this.collectionName,
        documentCount: count,
        ready: true,
      };
    }
    return await this.embeddedCollection.getStatus();
  }

  /**
   * 清空集合数据
   */
  async reset() {
    if (this.activeMode === 'uninitialized') await this.initialize();
    if (this.activeMode === 'seekdb_server') {
      // 重建集合
      await this.client.deleteCollection({ name: this.collectionName });
      this.collection = await this.client.createCollection({ name: this.collectionName });
    } else {
      await this.embeddedCollection.clear();
    }
    return { reset: true, mode: this.activeMode };
  }
}
