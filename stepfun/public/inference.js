/**
 * 端侧 AI 推理引擎 (Edge AI Inference Module)
 * 使用 Transformers.js 在浏览器端侧本地执行 Embedding 向量化。
 * 100% 本地运算，优先调度 WebGPU 硬件加速，自动降级至 WASM，支持 INT8 量化与 FP32/FP16 对比。
 */

// 动态导入 Transformers.js ESM
let transformersModule = null;
let pipelineInstance = null;

export const InferenceState = {
  modelName: 'Xenova/all-MiniLM-L6-v2',
  quantized: true, // INT8 量化
  activeBackend: 'detecting', // 'webgpu' | 'wasm'
  webgpuSupported: false,
  isLoaded: false,
  loadDurationMs: 0,
  modelSizeBytes: 23 * 1024 * 1024, // ~23MB for INT8
  embeddingDim: 384,
};

// 模型元数据统计表 (用于体积、压缩比与维度对比)
export const MODEL_SPECS = {
  'Xenova/all-MiniLM-L6-v2': {
    fp32SizeMB: 90.5,
    int8SizeMB: 23.2,
    compressionRatio: 3.9,
    dimension: 384,
    description: '社区经典轻量级英文/代码模型，seekdb-js 官方标准预设',
  },
  'Xenova/bge-small-zh-v1.5': {
    fp32SizeMB: 95.8,
    int8SizeMB: 25.1,
    compressionRatio: 3.82,
    dimension: 512,
    description: 'BAAI 中文增强语义检索模型，针对中文同义词和行业术语调优',
  },
};

/**
 * 检测当前浏览器与显卡是否支持 WebGPU
 */
export async function detectWebGPUSupport() {
  if (typeof navigator !== 'undefined' && 'gpu' in navigator) {
    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (adapter) {
        InferenceState.webgpuSupported = true;
        return true;
      }
    } catch (e) {
      console.warn('[EdgeAI] WebGPU 检测受限:', e);
    }
  }
  InferenceState.webgpuSupported = false;
  return false;
}

/**
 * 初始化端侧推理流水线 (支持指定 WebGPU / WASM 及 INT8 量化)
 */
export async function initInferenceEngine({
  modelName = 'Xenova/all-MiniLM-L6-v2',
  quantized = true,
  preferBackend = 'auto', // 'auto' | 'webgpu' | 'wasm'
  onProgress = null,
} = {}) {
  const startTime = performance.now();
  InferenceState.modelName = modelName;
  InferenceState.quantized = quantized;

  const spec = MODEL_SPECS[modelName] || {
    fp32SizeMB: 90,
    int8SizeMB: 23,
    compressionRatio: 3.9,
    dimension: 384,
  };
  InferenceState.embeddingDim = spec.dimension;
  InferenceState.modelSizeBytes = (quantized ? spec.int8SizeMB : spec.fp32SizeMB) * 1024 * 1024;

  // 1. 探测 WebGPU
  const hasWebGPU = await detectWebGPUSupport();
  let targetDevice = 'wasm';

  if (preferBackend === 'webgpu' && hasWebGPU) {
    targetDevice = 'webgpu';
  } else if (preferBackend === 'auto') {
    targetDevice = hasWebGPU ? 'webgpu' : 'wasm';
  } else {
    targetDevice = 'wasm';
  }

  // 2. 加载 Transformers.js
  if (!transformersModule) {
    try {
      transformersModule = await import('https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2');
      transformersModule.env.allowLocalModels = false;
      transformersModule.env.useBrowserCache = true;
    } catch (err) {
      console.error('[EdgeAI] Transformers.js 加载失败:', err);
      throw new Error(`无法载入端侧推理运行时: ${err.message}`);
    }
  }

  const { pipeline } = transformersModule;

  // 3. 尝试以指定后端加载模型；若 WebGPU 失败则自动优雅降级到 WASM
  try {
    console.log(`[EdgeAI] 正在初始化端侧模型: ${modelName} (quantized=${quantized}, device=${targetDevice})...`);
    pipelineInstance = await pipeline('feature-extraction', modelName, {
      quantized,
      device: targetDevice,
      progress_callback: onProgress,
    });
    InferenceState.activeBackend = targetDevice;
  } catch (err) {
    if (targetDevice === 'webgpu') {
      console.warn(`[EdgeAI] WebGPU 初始化异常 (${err.message})，正在自动平滑降级至 WASM 后端...`);
      targetDevice = 'wasm';
      pipelineInstance = await pipeline('feature-extraction', modelName, {
        quantized,
        device: 'wasm',
        progress_callback: onProgress,
      });
      InferenceState.activeBackend = 'wasm';
    } else {
      throw err;
    }
  }

  InferenceState.isLoaded = true;
  InferenceState.loadDurationMs = Math.round(performance.now() - startTime);
  console.log(`[EdgeAI] 模型初始化完成! 活跃后端: ${InferenceState.activeBackend.toUpperCase()}, 耗时: ${InferenceState.loadDurationMs}ms`);

  return {
    ...InferenceState,
    spec,
  };
}

/**
 * 对单条文本执行本地向量化 (含 Mean-Pooling 与 L2 归一化)
 */
export async function encodeText(text) {
  if (!pipelineInstance) {
    await initInferenceEngine({
      modelName: InferenceState.modelName,
      quantized: InferenceState.quantized,
    });
  }

  const startTime = performance.now();
  // 执行端侧特征抽取 (pooling: 'mean', normalize: true 保证余弦相似度等于点积)
  const output = await pipelineInstance(text, {
    pooling: 'mean',
    normalize: true,
  });

  const durationMs = performance.now() - startTime;
  const embedding = Array.from(output.data);

  return {
    embedding,
    dimension: embedding.length,
    durationMs,
  };
}

/**
 * 批量向量化 (Batch Processing)，带进度回调与吞吐率统计
 */
export async function encodeBatch(texts, { batchSize = 4, onProgress = null } = {}) {
  if (!pipelineInstance) {
    await initInferenceEngine({
      modelName: InferenceState.modelName,
      quantized: InferenceState.quantized,
    });
  }

  const startTime = performance.now();
  const total = texts.length;
  const embeddings = [];

  for (let i = 0; i < total; i += batchSize) {
    const chunk = texts.slice(i, i + batchSize);
    // 批次推理
    const batchPromises = chunk.map(txt => encodeText(txt));
    const chunkResults = await Promise.all(batchPromises);
    for (const res of chunkResults) {
      embeddings.push(res.embedding);
    }
    if (typeof onProgress === 'function') {
      onProgress({
        processed: embeddings.length,
        total,
        percentage: Math.round((embeddings.length / total) * 100),
      });
    }
  }

  const totalDurationMs = performance.now() - startTime;
  const throughput = total > 0 ? (total / (totalDurationMs / 1000)).toFixed(1) : 0;

  return {
    embeddings,
    totalDurationMs,
    throughputDocsPerSec: parseFloat(throughput),
  };
}
