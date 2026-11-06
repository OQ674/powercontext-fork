"""对 Dify DSL 做离线结构自检（不需要 Dify 实例）。

检查项：
  1. YAML 可解析、kind/version/mode 存在；
  2. 节点 id 唯一，边的两端都存在，出边句柄合法（source / true / false）；
  3. 从 start 能走到所有节点，且至少有一个 answer 节点；
  4. prompt / answer / http body 里引用的 {{#node.field#}} 节点确实存在。

用法：
    python scripts/validate_dsl.py dify/grudge-tavern.dsl.yml
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict, deque
from pathlib import Path

import yaml

REF_RE = re.compile(r"\{\{#([A-Za-z0-9_\-]+)\.([A-Za-z0-9_\-\.]+)#\}\}")


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from walk_strings(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_strings(item)


def main(path: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        print("[FAIL] DSL 根节点不是对象")
        return 1

    for key in ("app", "kind", "version", "workflow"):
        if key not in doc:
            errors.append(f"缺少顶层字段 {key}")
    app = doc.get("app") or {}
    mode = app.get("mode")
    if mode != "advanced-chat":
        warnings.append(f"app.mode={mode}，本 DSL 预期为 advanced-chat")

    graph = (doc.get("workflow") or {}).get("graph") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if not nodes:
        errors.append("graph.nodes 为空")
    if not edges:
        errors.append("graph.edges 为空")

    ids: dict[str, dict] = {}
    for node in nodes:
        nid = str(node.get("id"))
        if nid in ids:
            errors.append(f"节点 id 重复：{nid}")
        ids[nid] = node

    node_type = {nid: (n.get("data") or {}).get("type") for nid, n in ids.items()}

    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        src = str(edge.get("source"))
        tgt = str(edge.get("target"))
        handle = str(edge.get("sourceHandle") or "source")
        if src not in ids:
            errors.append(f"边引用了不存在的源节点：{src}")
            continue
        if tgt not in ids:
            errors.append(f"边引用了不存在的目标节点：{tgt}")
            continue
        valid_handles = {"source", "true", "false"}
        if handle not in valid_handles:
            errors.append(f"边 {src}->{tgt} 的 sourceHandle 非法：{handle}")
        if node_type[src] == "if-else" and handle not in {"true", "false"}:
            errors.append(f"if-else 节点 {src} 的出边必须用 true/false 句柄")
        if node_type[src] != "if-else" and handle != "source":
            errors.append(f"普通节点 {src} 的出边句柄应为 source，实际 {handle}")
        adj[src].append(tgt)

    if "start" not in ids:
        errors.append("缺少 start 节点")
    else:
        seen = {"start"}
        queue = deque(["start"])
        while queue:
            cur = queue.popleft()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        unreachable = sorted(set(ids) - seen)
        if unreachable:
            errors.append(f"从 start 不可达的节点：{unreachable}")

    answers = [nid for nid, t in node_type.items() if t == "answer"]
    if not answers:
        errors.append("缺少 answer 节点")

    if_else_nodes = [nid for nid, t in node_type.items() if t == "if-else"]
    for nid in if_else_nodes:
        handles = {str(e.get("sourceHandle")) for e in edges if str(e.get("source")) == nid}
        if handles != {"true", "false"}:
            errors.append(f"if-else 节点 {nid} 的分支应为 true/false 各一条，实际 {sorted(handles)}")

    known_vars = set(ids) | {"sys", "env", "conversation"}
    refs: set[tuple[str, str]] = set()
    for text in walk_strings(doc):
        for node_ref, var_ref in REF_RE.findall(text):
            refs.add((node_ref, var_ref))
            if node_ref not in known_vars:
                errors.append(f"变量引用指向不存在的节点：{{{{#{node_ref}.{var_ref}#}}}}")

    print(f"文件：{path}")
    print(f"应用：{app.get('name')}  mode={mode}  DSL version={doc.get('version')}")
    print(f"节点：{len(nodes)}  连线：{len(edges)}  变量引用：{len(refs)}")
    for node in nodes:
        data = node.get("data") or {}
        print(f"  - {node.get('id'):<14} {data.get('type'):<14} {data.get('title')}")

    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        print("\n[FAIL] 发现结构问题：")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\n[OK] DSL 结构自检通过（仍需在 Dify 中实际导入并试跑）")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dify/grudge-tavern.dsl.yml")
    raise SystemExit(main(target))
