/* SeekLit 前端：实时 seekdb 优先；不可达时切到明确标注的只读样例快照。 */
"use strict";

const API = "/functions/v1/app";
const API_TIMEOUT_MS = 4500;
let serviceMode = "checking"; // checking | live | sample
let samplePapers = [];

function setServiceMode(next) {
  serviceMode = next;
  const banner = document.getElementById("offline-banner");
  const status = document.getElementById("service-status");
  banner.classList.toggle("hidden", next !== "sample");
  status.className = `service-status ${next}`;
  status.innerHTML = `<span class="status-dot"></span>${next === "live" ? "seekdb 实时" : next === "sample" ? "本地样例" : "连接 seekdb…"}`;
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const resp = await fetch(`${API}${path}`, {
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      ...options,
      signal: controller.signal,
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.status === 503 && data.code === "BACKEND_OFFLINE") throw new Error("BACKEND_OFFLINE");
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    return data;
  } catch (error) {
    if (error.name === "AbortError" || error.message === "Failed to fetch") throw new Error("BACKEND_OFFLINE");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function toast(msg) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function mode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

const MODE_HINTS = {
  hybrid: "向量 + 全文 RRF 融合",
  semantic: "语义向量检索（IVF cosine）",
  keyword: "ik 全文关键词检索",
};
document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    updateModeHint();
    const q = document.getElementById("q").value;
    if (q) doSearch(q);
  });
});

function highlight(text, query) {
  let out = esc(text);
  const terms = String(query).split(/\s+/).filter((word) => word.length > 1);
  for (const term of terms) {
    out = out.replace(new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"), "<b>$1</b>");
  }
  return out;
}

function hitCard(hit, query) {
  const p = hit.paper;
  const badges = hit.sources.map((source) => {
    if (source === "sample") return '<span class="badge sample">本地样例</span>';
    const label = source === "vector" ? `向量 #${hit.vector_rank ?? "-"}`
      : source === "fulltext" ? `全文 #${hit.fulltext_rank ?? "-"}` : "融合";
    return `<span class="badge ${esc(source)}">${label}</span>`;
  }).join("");
  const sample = p.is_sample && !hit.sources.includes("sample") ? '<span class="badge sample">样例</span>' : "";
  const titleHtml = p.url
    ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>`
    : esc(p.title);
  const tags = (p.tags || []).map((tag) => `#${esc(tag)}`).join(" ");
  return `<article class="card">
    <div class="card-top">
      <span class="rank">#${hit.rank}</span>
      <span class="title">${titleHtml}</span>
      <span class="badges">${badges}${sample}</span>
    </div>
    <div class="meta">${esc(p.authors)} · ${esc(p.year)} · ${esc(p.venue)}${tags ? " · " + tags : ""}</div>
    ${p.abstract ? `<p class="abstract">${highlight(p.abstract.slice(0, 240), query)}${p.abstract.length > 240 ? "…" : ""}</p>` : ""}
  </article>`;
}

function currentFilters() {
  const tag = document.getElementById("tag-filter").value;
  return {
    year_min: +document.getElementById("year-min").value || null,
    year_max: +document.getElementById("year-max").value || null,
    venue: document.getElementById("venue-filter").value || null,
    tags: tag ? [tag] : null,
  };
}

async function doSearch(query) {
  query = String(query || "").trim();
  if (!query) return;
  const results = document.getElementById("results");
  const empty = document.getElementById("empty");
  results.innerHTML = '<div class="empty">检索中…</div>';
  empty.classList.add("hidden");

  if (serviceMode === "sample") {
    renderSampleResults(query);
    return;
  }

  try {
    const data = await api("/search", {
      method: "POST",
      body: JSON.stringify({ query, mode: mode(), n_results: 10, filters: currentFilters() }),
    });
    setServiceMode("live");
    renderHits(data.hits, query);
  } catch (error) {
    if (error.message !== "BACKEND_OFFLINE") {
      results.innerHTML = `<div class="empty">检索失败：${esc(error.message)}</div>`;
      return;
    }
    await ensureSamplePapers();
    setServiceMode("sample");
    updateModeHint();
    populateFilters(samplePapers);
    renderSampleResults(query);
  }
}

function renderHits(hits, query) {
  const results = document.getElementById("results");
  results.innerHTML = hits.length
    ? hits.map((hit) => hitCard(hit, query)).join("")
    : '<div class="empty">没有找到相关文献，换个说法或调整过滤条件试试。</div>';
}

function renderSampleResults(query) {
  const papers = sampleSearch(query, mode(), currentFilters()).slice(0, 10);
  const hits = papers.map((paper, index) => ({
    paper,
    rank: index + 1,
    sources: ["sample"],
    vector_rank: null,
    fulltext_rank: null,
  }));
  renderHits(hits, query);
}

function normalize(text) {
  return String(text || "").normalize("NFKC").toLowerCase();
}

const CONCEPTS = [
  { triggers: ["外部知识", "检索增强", "rag"], terms: ["rag", "检索增强", "外部知识", "知识密集", "retrieval-augmented"] },
  { triggers: ["大模型", "语言模型", "llm", "gpt"], terms: ["大语言模型", "语言模型", "gpt", "llm", "transformer"] },
  { triggers: ["向量", "相似", "embedding", "ann"], terms: ["向量检索", "embedding", "ann", "hnsw", "faiss", "相似性"] },
  { triggers: ["一致性", "共识", "paxos"], terms: ["一致性", "共识", "paxos", "分布式事务", "truetime"] },
  { triggers: ["缓存", "cache", "redis", "memcache"], terms: ["缓存", "cache", "redis", "memcache", "一致性哈希"] },
  { triggers: ["存储引擎", "lsm", "compaction"], terms: ["存储引擎", "lsm", "compaction", "rocksdb"] },
  { triggers: ["agent", "智能体", "工具调用"], terms: ["agent", "智能体", "工具调用", "mcp", "powercontext"] },
];

function literalTerms(query) {
  const q = normalize(query);
  const terms = new Set(q.match(/[a-z0-9][a-z0-9+_.-]{1,}|[\u3400-\u9fff]{2,}/g) || []);
  for (const block of q.match(/[\u3400-\u9fff]{3,}/g) || []) {
    for (let index = 0; index < block.length - 1; index++) terms.add(block.slice(index, index + 2));
  }
  return [...terms];
}

function expandedTerms(query) {
  const q = normalize(query);
  const terms = new Set(literalTerms(query));
  for (const concept of CONCEPTS) {
    if (concept.triggers.some((trigger) => q.includes(normalize(trigger)))) {
      concept.terms.forEach((term) => terms.add(normalize(term)));
    }
  }
  return [...terms];
}

function sampleSearch(query, searchMode, filters) {
  const q = normalize(query);
  const literal = literalTerms(query);
  const semantic = expandedTerms(query);
  return samplePapers
    .filter((paper) => (!filters.year_min || paper.year >= filters.year_min)
      && (!filters.year_max || paper.year <= filters.year_max)
      && (!filters.venue || paper.venue === filters.venue)
      && (!filters.tags || filters.tags.some((tag) => paper.tags.includes(tag))))
    .map((paper) => {
      const title = normalize(paper.title);
      const tags = normalize(paper.tags.join(" "));
      const abstract = normalize(paper.abstract);
      const all = `${title} ${tags} ${abstract}`;
      const keywordScore = (all.includes(q) ? 24 : 0)
        + literal.reduce((score, term) => score + (title.includes(term) ? 7 : 0) + (tags.includes(term) ? 6 : 0) + (abstract.includes(term) ? 2 : 0), 0);
      const semanticScore = semantic.reduce((score, term) => score + (title.includes(term) ? 5 : 0) + (tags.includes(term) ? 4 : 0) + (abstract.includes(term) ? 1 : 0), 0);
      const score = searchMode === "keyword" ? keywordScore : searchMode === "semantic" ? semanticScore : keywordScore * 1.15 + semanticScore;
      return { paper, score };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || b.paper.year - a.paper.year)
    .map((item) => item.paper);
}

document.getElementById("btn-search").addEventListener("click", () => doSearch(document.getElementById("q").value));
document.getElementById("q").addEventListener("keydown", (event) => {
  if (event.key === "Enter") doSearch(event.target.value);
});
document.querySelectorAll(".quick-query").forEach((button) => button.addEventListener("click", () => {
  document.getElementById("q").value = button.textContent;
  doSearch(button.textContent);
}));
document.getElementById("link-browse").addEventListener("click", (event) => {
  event.preventDefault();
  openManage("list");
});
document.getElementById("btn-retry-live").addEventListener("click", () => connectLive(true));

/* 管理弹窗 */
const dlg = document.getElementById("dlg-manage");
document.getElementById("btn-manage").addEventListener("click", () => openManage("add"));
document.getElementById("dlg-close").addEventListener("click", () => dlg.close());

function openManage(tab) {
  dlg.showModal();
  switchTab(tab);
  if (tab === "list") loadList("");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  document.querySelectorAll(".pane").forEach((pane) => pane.classList.toggle("active", pane.id === `pane-${name}`));
}
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  switchTab(tab.dataset.tab);
  if (tab.dataset.tab === "list") loadList(document.getElementById("list-q").value);
}));

function requireLiveWrite() {
  if (serviceMode === "live") return true;
  toast("本地样例为只读；实时 seekdb 恢复后才能写入");
  return false;
}

/* 新增 */
document.getElementById("form-add").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!requireLiveWrite()) return;
  const body = {
    title: document.getElementById("f-title").value,
    authors: document.getElementById("f-authors").value,
    year: +document.getElementById("f-year").value || 2024,
    venue: document.getElementById("f-venue").value,
    tags: document.getElementById("f-tags").value.split(/[;；]/).map((value) => value.trim()).filter(Boolean),
    language: document.getElementById("f-lang").value,
    abstract: document.getElementById("f-abstract").value,
    url: document.getElementById("f-url").value,
  };
  try {
    await api("/papers", { method: "POST", body: JSON.stringify(body) });
    toast("已保存并重建索引");
    event.target.reset();
    document.getElementById("f-year").value = 2024;
  } catch (error) {
    if (error.message === "BACKEND_OFFLINE") setServiceMode("sample");
    toast(error.message === "BACKEND_OFFLINE" ? "实时后端离线，无法保存" : "保存失败");
  }
});

/* 列表 + 删除 */
async function loadList(q) {
  const box = document.getElementById("paper-list");
  box.innerHTML = '<div class="small">加载中…</div>';
  if (serviceMode === "sample") {
    await ensureSamplePapers();
    const needle = normalize(q);
    const papers = samplePapers.filter((paper) => !needle || normalize(paper.title).includes(needle));
    box.innerHTML = papers.length
      ? papers.map((paper) => `<div class="paper-item"><span>${esc(paper.title)} <span class="small">(${esc(paper.year)}) · 本地样例</span></span></div>`).join("")
      : '<div class="small">暂无文献</div>';
    return;
  }
  try {
    const data = await api(`/papers?page=1&page_size=100${q ? `&q=${encodeURIComponent(q)}` : ""}`);
    box.innerHTML = data.papers.length
      ? data.papers.map((paper) => `<div class="paper-item">
          <span>${esc(paper.title)} <span class="small">(${esc(paper.year)})</span></span>
          <button class="del" data-id="${esc(paper.id)}">删除</button>
        </div>`).join("")
      : '<div class="small">暂无文献</div>';
    box.querySelectorAll(".del").forEach((button) => button.addEventListener("click", async () => {
      try {
        await api(`/papers/${button.dataset.id}`, { method: "DELETE" });
        toast("已删除");
        loadList(document.getElementById("list-q").value);
      } catch { toast("删除失败"); }
    }));
  } catch {
    setServiceMode("sample");
    loadList(q);
  }
}
document.getElementById("list-q").addEventListener("input", (event) => loadList(event.target.value));

/* CSV 导入 */
document.getElementById("btn-import").addEventListener("click", async () => {
  const text = document.getElementById("csv-text").value.trim();
  const out = document.getElementById("import-result");
  if (!text) { out.textContent = "请先粘贴 CSV 内容"; return; }
  if (!requireLiveWrite()) { out.textContent = "本地样例为只读，实时 seekdb 恢复后才能导入"; return; }
  const items = parseCsv(text);
  if (!items.length) { out.textContent = "未解析到有效数据行"; return; }
  try {
    const data = await api("/import", { method: "POST", body: JSON.stringify({ items }) });
    out.textContent = `成功导入 ${data.imported} 条`;
    document.getElementById("csv-text").value = "";
  } catch (error) {
    out.textContent = error.message === "BACKEND_OFFLINE" ? "实时后端离线，无法导入" : "导入失败";
  }
});

function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) return [];
  const header = splitCsvLine(lines[0]).map((value) => value.trim().toLowerCase());
  return lines.slice(1).map((line) => {
    const vals = splitCsvLine(line);
    const obj = {};
    header.forEach((name, index) => { if (name) obj[name] = (vals[index] || "").trim(); });
    return {
      id: obj.id || "",
      title: obj.title || "",
      authors: obj.authors || "",
      year: +obj.year || 2024,
      venue: obj.venue || "",
      tags: String(obj.tags || "").split(/[;；]/).map((value) => value.trim()).filter(Boolean),
      language: obj.language || "zh",
      abstract: obj.abstract || "",
      url: obj.url || "",
      is_sample: String(obj.is_sample).toLowerCase() !== "false",
    };
  }).filter((item) => item.title);
}

function splitCsvLine(line) {
  const out = [];
  let cur = "", inQuotes = false;
  for (let index = 0; index < line.length; index++) {
    const char = line[index];
    if (inQuotes) {
      if (char === '"' && line[index + 1] === '"') { cur += '"'; index++; }
      else if (char === '"') inQuotes = false;
      else cur += char;
    } else if (char === '"') inQuotes = true;
    else if (char === ",") { out.push(cur); cur = ""; }
    else cur += char;
  }
  out.push(cur);
  return out;
}

async function ensureSamplePapers() {
  if (samplePapers.length) return samplePapers;
  const resp = await fetch("papers.csv", { cache: "force-cache" });
  if (!resp.ok) throw new Error("样例快照加载失败");
  samplePapers = parseCsv(await resp.text());
  return samplePapers;
}

function populateFilters(papers) {
  const tagSel = document.getElementById("tag-filter");
  const venueSel = document.getElementById("venue-filter");
  const currentTag = tagSel.value;
  const currentVenue = venueSel.value;
  const tags = new Set(), venues = new Set();
  papers.forEach((paper) => {
    (paper.tags || []).forEach((tag) => tags.add(tag));
    if (paper.venue) venues.add(paper.venue);
  });
  tagSel.replaceChildren(new Option("全部", ""));
  venueSel.replaceChildren(new Option("全部", ""));
  [...tags].sort().forEach((tag) => tagSel.add(new Option(tag, tag)));
  [...venues].sort().forEach((venue) => venueSel.add(new Option(venue, venue)));
  if ([...tags].includes(currentTag)) tagSel.value = currentTag;
  if ([...venues].includes(currentVenue)) venueSel.value = currentVenue;
}

function updateModeHint() {
  document.getElementById("mode-hint").textContent = serviceMode === "sample"
    ? `${MODE_HINTS[mode()]} · 当前为只读样例近似排序`
    : MODE_HINTS[mode()];
}

async function connectLive(showToast = false) {
  setServiceMode("checking");
  updateModeHint();
  try {
    const health = await api("/health");
    const data = await api("/papers?page=1&page_size=100");
    setServiceMode("live");
    document.title = `SeekLit · ${health.papers} 篇文献`;
    populateFilters(data.papers);
    if (showToast) toast("已恢复 seekdb 实时服务");
    return true;
  } catch {
    await ensureSamplePapers();
    setServiceMode("sample");
    document.title = `SeekLit · ${samplePapers.length} 篇本地样例`;
    populateFilters(samplePapers);
    if (showToast) toast("实时服务仍不可达，继续使用本地样例");
    return false;
  } finally {
    updateModeHint();
    document.getElementById("empty").classList.remove("hidden");
  }
}

["tag-filter", "venue-filter", "year-min", "year-max"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => {
    const q = document.getElementById("q").value;
    if (q) doSearch(q);
  });
});

(async function init() {
  await Promise.allSettled([ensureSamplePapers(), connectLive(false)]);
})();
