"""上下文包组装。

输出分两部分：

* ``JSON``：机器可读，供 Agent / 自动化流程使用；
* ``Markdown``：直接进入 MiniMax 提示词的人类可读版本。

输出中每一条规格 / 代码 / 测试都带**真实来源**（文件路径、node id、规格版本号）。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .db import Database
from .models import RetrievedItem, TaskState
from .retriever import Retriever


def build_context_bundle(
    database: Database,
    task_id: str,
    title: str,
    description: str = "",
    *,
    state: Optional[TaskState] = None,
    spec_limit: int = 6,
    code_limit: int = 12,
    test_limit: int = 12,
) -> Dict[str, Any]:
    """根据任务描述组装上下文包。"""

    task_text = f"{title}\n{description}".strip()
    retriever = Retriever(database)

    specs = retriever.retrieve_specs(task_text, task_id=task_id, limit=spec_limit)
    code = retriever.retrieve_code(task_text, specs, task_id=task_id, limit=code_limit)
    tests = retriever.retrieve_tests(task_text, specs, code, task_id=task_id, limit=test_limit)

    database.execute(
        """
        INSERT INTO sdd_task (task_id, title, description, status, created_at, updated_at)
        VALUES (%s, %s, %s, 'in_progress', NOW(), NOW())
        ON DUPLICATE KEY UPDATE title = VALUES(title), description = VALUES(description), updated_at = NOW()
        """,
        (task_id, title, description),
    )

    bundle: Dict[str, Any] = {
        "task": {
            "task_id": task_id,
            "title": title,
            "description": description,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
        "database": database.describe(),
        "specs": [_spec_entry(item) for item in specs],
        "code": [_code_entry(item) for item in code],
        "tests": [_test_entry(item) for item in tests],
        "task_state": state.to_dict() if state else None,
        "citations": _citations(specs, code, tests),
    }
    bundle["markdown"] = render_markdown(bundle)
    return bundle


def _spec_entry(item: RetrievedItem) -> Dict[str, Any]:
    payload = dict(item.payload)
    return {
        "spec_id": item.ref,
        "title": payload.get("title", ""),
        "module": payload.get("module", ""),
        "status": payload.get("status", ""),
        "revision": payload.get("revision", 1),
        "source_file": payload.get("source_file", ""),
        "body": payload.get("body", ""),
        "keywords": payload.get("keywords", ""),
        "related_code": payload.get("related_code", ""),
        "related_tests": payload.get("related_tests", ""),
        "reasons": item.reasons,
        "score": item.score,
    }


def _code_entry(item: RetrievedItem) -> Dict[str, Any]:
    payload = dict(item.payload)
    return {
        "file_path": payload.get("file_path", ""),
        "symbol": payload.get("symbol", ""),
        "kind": payload.get("kind", ""),
        "signature": payload.get("signature", ""),
        "docstring": payload.get("docstring", ""),
        "line_start": payload.get("line_start", 0),
        "line_end": payload.get("line_end", 0),
        "source_file": payload.get("source_file", ""),
        "reasons": item.reasons,
        "score": item.score,
    }


def _test_entry(item: RetrievedItem) -> Dict[str, Any]:
    payload = dict(item.payload)
    return {
        "node_id": item.ref,
        "file_path": payload.get("file_path", ""),
        "test_name": payload.get("test_name", ""),
        "purpose": payload.get("purpose", ""),
        "markers": payload.get("markers", ""),
        "source_file": payload.get("source_file", ""),
        "reasons": item.reasons,
        "score": item.score,
    }


def _citations(
    specs: List[RetrievedItem],
    code: List[RetrievedItem],
    tests: List[RetrievedItem],
) -> List[Dict[str, str]]:
    citations: List[Dict[str, str]] = []
    for item in specs:
        citations.append(
            {
                "kind": "spec",
                "ref": item.ref,
                "source": str(item.payload.get("source_file", "")),
                "revision": str(item.payload.get("revision", "")),
            }
        )
    for item in code:
        citations.append(
            {
                "kind": "code",
                "ref": item.ref,
                "source": str(item.payload.get("source_file", "")),
                "revision": "",
            }
        )
    for item in tests:
        citations.append(
            {
                "kind": "test",
                "ref": item.ref,
                "source": str(item.payload.get("source_file", "")),
                "revision": "",
            }
        )
    return citations


def render_markdown(bundle: Dict[str, Any]) -> str:
    """把上下文包渲染为进入 MiniMax 提示词的 Markdown。"""

    task = bundle.get("task", {})
    lines: List[str] = []
    lines.append(f"# 开发任务：{task.get('title', '')}")
    lines.append("")
    lines.append(f"- 任务 ID：{task.get('task_id', '')}")
    if task.get("description"):
        lines.append(f"- 任务描述：{task['description']}")
    database = bundle.get("database", {})
    lines.append(f"- 上下文来源数据库：{database.get('backend', '')}（{database.get('server_version', '')}）")
    lines.append("")

    specs = bundle.get("specs", [])
    lines.append("## 一、本次任务适用的规格")
    if not specs:
        lines.append("（无匹配规格）")
    for spec in specs:
        lines.append("")
        title = str(spec["title"])
        if title.startswith(spec["spec_id"]):
            title = title[len(spec["spec_id"]) :].strip()
        lines.append(f"### {spec['spec_id']} {title}")
        lines.append(
            f"- 来源文件：`{spec['source_file']}`（第 {spec['revision']} 版，状态：{spec['status']}）"
        )
        lines.append(f"- 关联代码：`{spec['related_code']}`")
        lines.append(f"- 关联测试：`{spec['related_tests']}`")
        lines.append(f"- 命中原因：{'；'.join(spec['reasons'])}")
        lines.append("")
        lines.append("```text")
        lines.append(spec["body"].strip())
        lines.append("```")
    lines.append("")

    code = bundle.get("code", [])
    lines.append("## 二、需要修改的代码文件与符号")
    if not code:
        lines.append("（无匹配代码）")
    for entry in code:
        lines.append(
            f"- `{entry['file_path']}` :: `{entry['symbol']}`（{entry['kind']}，"
            f"L{entry['line_start']}-L{entry['line_end']}） — {'；'.join(entry['reasons'])}"
        )
        if entry["signature"]:
            lines.append(f"  - 签名：`{entry['signature']}`")
    lines.append("")

    tests = bundle.get("tests", [])
    lines.append("## 三、用于验证功能与兼容性的测试")
    if not tests:
        lines.append("（无匹配测试）")
    for entry in tests:
        lines.append(f"- `{entry['node_id']}` — {entry['purpose'] or '（无说明）'} — {'；'.join(entry['reasons'])}")
    lines.append("")

    state = bundle.get("task_state")
    lines.append("## 四、已完成事项、待办事项与已有验证结果")
    if not state:
        lines.append("（暂无历史状态）")
    else:
        lines.append(f"- 状态来源：{state.get('origin') or 'unknown'}")
        for item in state.get("done", []):
            lines.append(f"- [已完成] {item}")
        for item in state.get("todo", []):
            lines.append(f"- [待办] {item}")
        for item in state.get("verifications", []):
            lines.append(
                f"- [验证] {item.get('phase', '')} {item.get('command', '')} "
                f"→ 退出码 {item.get('exit_code')}, 通过 {item.get('passed')}, 失败 {item.get('failed')}"
            )
        for item in state.get("notes", []):
            lines.append(f"- [备注] {item}")
    lines.append("")
    return "\n".join(lines)


def dump_json(bundle: Dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, indent=2)
