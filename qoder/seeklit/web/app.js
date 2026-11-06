/* SeekLit 前端：唯一请求出口 + UI 逻辑（零依赖） */
"use strict";

const API = "/functions/v1/app";
let offline = false;

async function api(path, options = {}) {
  const resp = await fetch(`${API}${path}`, {
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    ...options,
  });
  const data = await resp.json().catch(() => ({}));
  if (resp.status === 503 && data.code === "BACKEND_OFFLINE") {
    setOffline(true);
    throw new Error("BACKEND_OFFLINE");
  }
  if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
  return data;
}

function setOffline(flag) {
  offline = flag;
  document.getElementById("offline-banner").classList.toggle("hidden", !flag);
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
document.querySelectorAll('input[name="mode"]').forEach((r) => {
  r.addEventListener("change", () => {
    document.getElementById("mode-hint").textContent = MODE_HINTS[mode()];
  });
});

function highlight(text, query) {
  const t = esc(text);
  if (!query) return t;
  const terms = query.split(/\s+/).filter((w) => w.length > 1);
  let out = t;
  for (const term of terms) out = out.replace(new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "g"), "<b>$1</b>");
  return out;
}

function hitCard(hit, query) {
  const p = hit.paper;
  const badges = hit.sources.map((s) => {
    const label = s === "vector" ? `向量 #${hit.vector_rank ?? "-"}` : s === "fulltext" ? `全文 #${hit.fulltext_rank ?? "-"}` : "融合";
    return `<span class="badge ${esc(s)}">${label}</span>`;
  }).join("");
  const sample = p.is_sample ? `<span class="badge sample">样例</span>` : "";
  const titleHtml = p.url
    ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>`
    : esc(p.title);
  const tags = (p.tags || []).map((t) => `#${esc(t)}`).join(" ");
  return `<article class="card">
    <div class="card-top">
      <span class="rank">#${hit.rank}</span>
      <span class="title">${titleHtml}</span>
      <span class="badges">${badges}${sample}</span>
    </div>
    <div class="meta">${esc(p.authors)} · ${esc(p.year)} · ${esc(p.venue)}${tags ? " · " + tags : ""}</div>
    ${p.abstract ? `<p class="abstract">${highlight(p.abstract.slice(0, 220), query)}${p.abstract.length > 220 ? "…" : ""}</p>` : ""}
  </article>`;
}

async function doSearch(query) {
  if (!query.trim()) return;
  const results = document.getElementById("results");
  const empty = document.getElementById("empty");
  results.innerHTML = `<div class="empty">检索中…</div>`;
  empty.classList.add("hidden");
  const body = {
    query,
    mode: mode(),
    n_results: 10,
    filters: {
      year_min: +document.getElementById("year-min").value || null,
      year_max: +document.getElementById("year-max").value || null,
      venue: document.getElementById("venue-filter").value || null,
    },
  };
  try {
    const data = await api("/search", { method: "POST", body: JSON.stringify(body) });
    results.innerHTML = data.hits.length
      ? data.hits.map((h) => hitCard(h, query)).join("")
      : `<div class="empty">没有找到相关文献，换个说法试试（语义检索支持概念性描述）。</div>`;
  } catch (e) {
    if (e.message !== "BACKEND_OFFLINE") results.innerHTML = `<div class="empty">检索失败：${esc(e.message)}</div>`;
    else results.innerHTML = "";
  }
}

document.getElementById("btn-search").addEventListener("click", () => doSearch(document.getElementById("q").value));
document.getElementById("q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch(e.target.value);
});
document.getElementById("link-browse").addEventListener("click", (e) => {
  e.preventDefault();
  openManage("list");
});

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
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("active", p.id === `pane-${name}`));
}
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  switchTab(t.dataset.tab);
  if (t.dataset.tab === "list") loadList(document.getElementById("list-q").value);
}));

/* 新增 */
document.getElementById("form-add").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    title: document.getElementById("f-title").value,
    authors: document.getElementById("f-authors").value,
    year: +document.getElementById("f-year").value || 2024,
    venue: document.getElementById("f-venue").value,
    tags: document.getElementById("f-tags").value.split(/[;；]/).map((s) => s.trim()).filter(Boolean),
    language: document.getElementById("f-lang").value,
    abstract: document.getElementById("f-abstract").value,
    url: document.getElementById("f-url").value,
  };
  try {
    await api("/papers", { method: "POST", body: JSON.stringify(body) });
    toast("已保存并重建索引");
    e.target.reset();
    document.getElementById("f-year").value = 2024;
  } catch (err) {
    toast(err.message === "BACKEND_OFFLINE" ? "后端离线，无法保存" : "保存失败");
  }
});

/* 列表 + 删除 */
async function loadList(q) {
  const box = document.getElementById("paper-list");
  box.innerHTML = `<div class="small">加载中…</div>`;
  try {
    const data = await api(`/papers?page=1&page_size=100${q ? `&q=${encodeURIComponent(q)}` : ""}`);
    box.innerHTML = data.papers.length
      ? data.papers.map((p) => `<div class="paper-item">
          <span>${esc(p.title)} <span class="small">(${esc(p.year)})</span></span>
          <button class="del" data-id="${esc(p.id)}">删除</button>
        </div>`).join("")
      : `<div class="small">暂无文献</div>`;
    box.querySelectorAll(".del").forEach((b) => b.addEventListener("click", async () => {
      try {
        await api(`/papers/${b.dataset.id}`, { method: "DELETE" });
        toast("已删除");
        loadList(document.getElementById("list-q").value);
      } catch { toast("删除失败"); }
    }));
  } catch {
    box.innerHTML = `<div class="small">后端离线</div>`;
  }
}
document.getElementById("list-q").addEventListener("input", (e) => loadList(e.target.value));

/* CSV 导入 */
document.getElementById("btn-import").addEventListener("click", async () => {
  const text = document.getElementById("csv-text").value.trim();
  const out = document.getElementById("import-result");
  if (!text) { out.textContent = "请先粘贴 CSV 内容"; return; }
  const items = parseCsv(text);
  if (!items.length) { out.textContent = "未解析到有效数据行"; return; }
  try {
    const data = await api("/import", { method: "POST", body: JSON.stringify({ items }) });
    out.textContent = `成功导入 ${data.imported} 条`;
    document.getElementById("csv-text").value = "";
  } catch (e) {
    out.textContent = e.message === "BACKEND_OFFLINE" ? "后端离线，无法导入" : "导入失败";
  }
});

function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return [];
  const header = splitCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
  return lines.slice(1).map((line) => {
    const vals = splitCsvLine(line);
    const obj = {};
    header.forEach((h, i) => { if (h) obj[h] = (vals[i] || "").trim(); });
    return {
      title: obj.title || "",
      authors: obj.authors || "",
      year: +obj.year || 2024,
      venue: obj.venue || "",
      tags: obj.tags || "",
      language: obj.language || "zh",
      abstract: obj.abstract || "",
      url: obj.url || "",
    };
  }).filter((it) => it.title);
}

function splitCsvLine(line) {
  const out = [];
  let cur = "", inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQ) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') inQ = false;
      else cur += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") { out.push(cur); cur = ""; }
    else cur += c;
  }
  out.push(cur);
  return out;
}

/* 初始化：探活 + 填充过滤下拉 */
(async function init() {
  try {
    const h = await api("/health");
    setOffline(false);
    document.title = `SeekLit · ${h.papers} 篇文献`;
    const data = await api("/papers?page=1&page_size=100");
    const tags = new Set(), venues = new Set();
    data.papers.forEach((p) => {
      (p.tags || []).forEach((t) => tags.add(t));
      if (p.venue) venues.add(p.venue);
    });
    const tagSel = document.getElementById("tag-filter");
    const venueSel = document.getElementById("venue-filter");
    [...tags].sort().forEach((t) => tagSel.add(new Option(t, t)));
    [...venues].sort().forEach((v) => venueSel.add(new Option(v, v)));
  } catch {
    setOffline(true);
  }
  tagFilterApply();
})();

function tagFilterApply() {
  document.getElementById("tag-filter").addEventListener("change", () => {
    const tag = document.getElementById("tag-filter").value;
    const yearMin = +document.getElementById("year-min").value || null;
    const yearMax = +document.getElementById("year-max").value || null;
    const q = document.getElementById("q").value;
    if (q) doSearch(q);
  });
}
