"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const projectRoot = path.resolve(__dirname, "..");
const elements = new Map();

class FakeClassList {
  constructor() { this.values = new Set(); }
  add(value) { this.values.add(value); }
  remove(value) { this.values.delete(value); }
  toggle(value, force) {
    if (force === undefined ? !this.values.has(value) : force) this.values.add(value);
    else this.values.delete(value);
  }
  contains(value) { return this.values.has(value); }
}

class FakeElement {
  constructor(id = "") {
    this.id = id;
    this.value = "";
    this.textContent = "";
    this.innerHTML = "";
    this.dataset = {};
    this.classList = new FakeClassList();
    this.options = [];
  }
  addEventListener() {}
  add(option) { this.options.push(option); }
  replaceChildren(...items) { this.options = items; }
  querySelectorAll() { return []; }
  appendChild() {}
  remove() {}
  reset() {}
  showModal() {}
  close() {}
}

function element(id) {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
}

const radio = new FakeElement("mode-hybrid");
radio.value = "hybrid";
const quickQueries = ["大模型如何利用外部知识", "分布式数据库一致性", "向量检索", "缓存"].map((text) => {
  const button = new FakeElement();
  button.textContent = text;
  return button;
});

for (const id of [
  "offline-banner", "service-status", "mode-hint", "tag-filter", "venue-filter", "year-min", "year-max",
  "results", "empty", "q", "btn-search", "link-browse", "btn-retry-live", "dlg-manage", "btn-manage",
  "dlg-close", "form-add", "f-title", "f-authors", "f-year", "f-venue", "f-tags", "f-lang", "f-abstract",
  "f-url", "paper-list", "list-q", "btn-import", "csv-text", "import-result",
]) element(id);

const csv = fs.readFileSync(path.join(projectRoot, "web", "papers.csv"), "utf8");
const context = {
  AbortController,
  console,
  setTimeout,
  clearTimeout,
  Option: function Option(text, value) { this.text = text; this.value = value; },
  fetch: async (url) => {
    if (url === "papers.csv") return { ok: true, text: async () => csv };
    return { ok: false, status: 503, json: async () => ({ code: "BACKEND_OFFLINE" }) };
  },
  document: {
    title: "SeekLit",
    body: element("body"),
    createElement: () => new FakeElement(),
    getElementById: element,
    querySelector: (selector) => selector === 'input[name="mode"]:checked' ? radio : null,
    querySelectorAll: (selector) => selector === 'input[name="mode"]' ? [radio]
      : selector === ".quick-query" ? quickQueries : [],
  },
};

vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(projectRoot, "web", "app.js"), "utf8"), context, { filename: "app.js" });

(async () => {
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.match(element("service-status").innerHTML, /本地样例/);
  await context.doSearch("大模型如何利用外部知识");
  assert.match(element("results").innerHTML, /检索增强生成技术综述/);
  assert.match(element("results").innerHTML, /本地样例/);
  assert.equal(context.sampleSearch("缓存", "hybrid", { year_min: null, year_max: null, venue: null, tags: null }).length > 0, true);
  assert.equal(context.sampleSearch("向量检索", "keyword", { year_min: 2026, year_max: null, venue: null, tags: ["seekdb"] })[0].id, "ai017");
  assert.equal(context.parseCsv(csv).length, 48);
  console.log("offline smoke test passed: 48 papers, fallback search and filters work");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
