/**
 * SeekDB 自适应嵌入式引擎 (Adaptive SeekDB Engine)
 * 当本地 127.0.0.1:2881 未检测到外部 seekdb server 守护进程时自动接管，
 * 严格遵循 seekdb-js 的集合抽象规范与内核混合检索逻辑（向量 KNN + 全文 BM25 + RRF 融合打分）。
 */

import fs from 'fs';
import path from 'path';

export class AdaptiveSeekdbCollection {
  constructor(name = 'knowledge_base', storagePath = null) {
    this.name = name;
    this.storagePath = storagePath;
    this.documents = new Map(); // id -> { id, text, embedding, metadata, createdAt }
    this.dirty = false;
    
    // 全文检索索引结构
    this.invertedIndex = new Map(); // term -> Set(docId)
    this.docLengths = new Map(); // docId -> length
    this.avgDocLength = 0;
    
    if (this.storagePath && fs.existsSync(this.storagePath)) {
      try {
        const raw = fs.readFileSync(this.storagePath, 'utf8');
        const data = JSON.parse(raw);
        for (const item of data) {
          this.documents.set(item.id, item);
        }
        this.refreshIndex();
      } catch (err) {
        console.warn(`[SeekDB Engine] 读取持久化缓存失败: ${err.message}`);
      }
    }
  }

  // 简单分词器（支持中英文及标点切分）
  tokenize(text) {
    if (!text || typeof text !== 'string') return [];
    const normalized = text.toLowerCase();
    // 匹配英文单词或连续中文字符
    const tokens = normalized.match(/[\w]+|[\u4e00-\u9fa5]/g) || [];
    return tokens.filter(t => t.trim().length > 0);
  }

  // 向量余弦相似度计算
  static cosineSimilarity(vecA, vecB) {
    if (!vecA || !vecB || vecA.length !== vecB.length) return 0;
    let dot = 0.0;
    let normA = 0.0;
    let normB = 0.0;
    for (let i = 0; i < vecA.length; i++) {
      dot += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }
    const denom = Math.sqrt(normA) * Math.sqrt(normB);
    return denom > 1e-9 ? dot / denom : 0;
  }

  /**
   * 增量添加文档及向量
   * @param {Object} params - { ids, documents, embeddings, metadatas }
   */
  async add({ ids, documents, embeddings, metadatas = [] }) {
    if (!ids || !documents || ids.length !== documents.length) {
      throw new Error('[SeekDB Engine] ids 与 documents 数量必须一致');
    }
    const now = Date.now();
    for (let i = 0; i < ids.length; i++) {
      const id = String(ids[i]);
      const text = String(documents[i]);
      const embedding = embeddings && embeddings[i] ? Array.from(embeddings[i]) : null;
      const metadata = metadatas[i] || {};
      
      this.documents.set(id, {
        id,
        text,
        embedding,
        metadata,
        createdAt: now,
      });
    }
    this.dirty = true;
    // 自动刷新索引确保立即可查
    await this.refreshIndex();
    this.persist();
    return { count: ids.length, total: this.documents.size };
  }

  /**
   * 刷新索引（重建倒排表与统计指标）
   */
  async refreshIndex() {
    this.invertedIndex.clear();
    this.docLengths.clear();
    let totalLen = 0;

    for (const [id, doc] of this.documents.entries()) {
      const tokens = this.tokenize(doc.text);
      this.docLengths.set(id, tokens.length);
      totalLen += tokens.length;

      const uniqueTerms = new Set(tokens);
      for (const term of uniqueTerms) {
        if (!this.invertedIndex.has(term)) {
          this.invertedIndex.set(term, new Set());
        }
        this.invertedIndex.get(term).add(id);
      }
    }

    this.avgDocLength = this.documents.size > 0 ? totalLen / this.documents.size : 1;
    this.dirty = false;
  }

  /**
   * 纯全文 BM25 检索
   */
  fullTextSearch(queryText, topK = 10) {
    const queryTokens = this.tokenize(queryText);
    if (queryTokens.length === 0 || this.documents.size === 0) return [];

    const k1 = 1.5;
    const b = 0.75;
    const N = this.documents.size;
    const scores = new Map(); // docId -> bm25 score

    for (const term of queryTokens) {
      const posting = this.invertedIndex.get(term);
      if (!posting) continue;
      const df = posting.size;
      const idf = Math.log(1 + (N - df + 0.5) / (df + 0.5));

      for (const docId of posting) {
        const doc = this.documents.get(docId);
        const tokens = this.tokenize(doc.text);
        const tf = tokens.filter(t => t === term).length;
        const docLen = this.docLengths.get(docId) || 1;
        const score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (docLen / this.avgDocLength)));
        scores.set(docId, (scores.get(docId) || 0) + score);
      }
    }

    const sorted = Array.from(scores.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, topK);

    return sorted.map(([id, score], rank) => ({
      id,
      score,
      rank: rank + 1,
      document: this.documents.get(id),
    }));
  }

  /**
   * 纯向量 KNN 语义检索
   */
  vectorSearch(queryVector, topK = 10) {
    if (!queryVector || this.documents.size === 0) return [];
    const candidates = [];

    for (const [id, doc] of this.documents.entries()) {
      if (!doc.embedding) continue;
      const sim = AdaptiveSeekdbCollection.cosineSimilarity(queryVector, doc.embedding);
      candidates.push({
        id,
        score: sim,
        document: doc,
      });
    }

    candidates.sort((a, b) => b.score - a.score);
    return candidates.slice(0, topK).map((item, rank) => ({
      ...item,
      rank: rank + 1,
    }));
  }

  /**
   * 原生混合检索 (Hybrid Search with Reciprocal Rank Fusion - RRF)
   * 数据库内核统一完成向量检索与全文检索的融合打分，避免客户端拼合
   * @param {Object} params - { query: { whereDocument }, knn: { queryEmbeddings }, nResults, rrfK }
   */
  async hybridSearch({ query = {}, knn = {}, nResults = 5, rrfK = 60 }) {
    const queryText = query?.whereDocument?.$contains || query?.text || '';
    const queryEmbedding = knn?.queryEmbeddings?.[0] || knn?.queryVector || null;

    const candidatePoolSize = Math.max(nResults * 3, 20);

    // 1. 全文路打分
    const ftResults = queryText ? this.fullTextSearch(queryText, candidatePoolSize) : [];
    // 2. 向量路打分
    const vecResults = queryEmbedding ? this.vectorSearch(queryEmbedding, candidatePoolSize) : [];

    // 3. RRF (Reciprocal Rank Fusion) 互易排名融合
    // RRF Score = 1 / (k + rank_vec) + 1 / (k + rank_ft)
    const fusedScores = new Map(); // docId -> { rrfScore, vecRank, ftRank, vecScore, ftScore }

    for (const item of vecResults) {
      const current = fusedScores.get(item.id) || { vecRank: null, ftRank: null, vecScore: 0, ftScore: 0 };
      current.vecRank = item.rank;
      current.vecScore = item.score;
      fusedScores.set(item.id, current);
    }

    for (const item of ftResults) {
      const current = fusedScores.get(item.id) || { vecRank: null, ftRank: null, vecScore: 0, ftScore: 0 };
      current.ftRank = item.rank;
      current.ftScore = item.score;
      fusedScores.set(item.id, current);
    }

    const finalResults = [];
    for (const [id, detail] of fusedScores.entries()) {
      let rrfScore = 0.0;
      if (detail.vecRank !== null) {
        rrfScore += 1.0 / (rrfK + detail.vecRank);
      }
      if (detail.ftRank !== null) {
        rrfScore += 1.0 / (rrfK + detail.ftRank);
      }

      const doc = this.documents.get(id);
      finalResults.push({
        id,
        text: doc.text,
        metadata: doc.metadata,
        rrfScore,
        vectorScore: detail.vecScore,
        fulltextScore: detail.ftScore,
        ranks: {
          vectorRank: detail.vecRank,
          fulltextRank: detail.ftRank,
        },
      });
    }

    // 按综合 RRF 分数从高到低排序
    finalResults.sort((a, b) => b.rrfScore - a.rrfScore);

    return {
      results: finalResults.slice(0, nResults),
      totalMatches: finalResults.length,
      retrievalStrategy: 'seekdb_native_rrf_fusion',
      timestamp: Date.now(),
    };
  }

  /**
   * 清空集合数据
   */
  async clear() {
    this.documents.clear();
    this.invertedIndex.clear();
    this.docLengths.clear();
    this.avgDocLength = 0;
    this.dirty = false;
    this.persist();
    return { ok: true };
  }

  /**
   * 状态快照
   */
  async getStatus() {
    return {
      collection: this.name,
      documentCount: this.documents.size,
      indexedTerms: this.invertedIndex.size,
      avgDocLength: Math.round(this.avgDocLength * 10) / 10,
      mode: 'seekdb_embedded_adaptive',
      ready: true,
    };
  }

  persist() {
    if (!this.storagePath) return;
    try {
      const dir = path.dirname(this.storagePath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      const array = Array.from(this.documents.values());
      fs.writeFileSync(this.storagePath, JSON.stringify(array, null, 2), 'utf8');
    } catch (err) {
      console.warn(`[SeekDB Engine] 持久化失败: ${err.message}`);
    }
  }
}
