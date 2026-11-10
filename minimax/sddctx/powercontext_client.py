"""PowerContext 客户端：任务状态的保存与复用。

只依赖标准库 ``urllib``，通过 PowerContext 的 HTTP API 接入：

* ``POST /v1/scopes``             —— 创建（或复用）任务 Scope。
* ``POST /v1/memory/remember``    —— 写入一条状态（已完成 / 待办 / 验证结果）。
* ``POST /v1/atomic-memory/list`` —— 读回 Scope 下的全部状态条目。
* ``POST /v1/memory/search``      —— 按任务 ID 检索状态条目。
* ``POST /v1/context/prepare``    —— 有界召回（可选）。
* ``GET  /health/ready``          —— 服务健康检查。

状态条目的正文采用固定前缀 ``[任务ID][类型] 内容``，读取时按该前缀解析，
因此即使 PowerContext 的检索模式退化为纯文本匹配，也能稳定读回状态。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .models import TaskState

_STATE_PATTERN = re.compile(r"^\[(?P<task>[^\]]+)\]\[(?P<kind>[^\]]+)\]\s*(?P<content>.*)$", re.S)


class PowerContextError(RuntimeError):
    """PowerContext 调用失败。"""


class PowerContextClient:
    """PowerContext HTTP 客户端。"""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Content-Type", "application/json; charset=utf-8")
        request.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover - 依赖服务端行为
            detail = exc.read().decode("utf-8", errors="replace")
            raise PowerContextError(f"{method} {path} 失败：HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover
            raise PowerContextError(f"{method} {path} 失败：{exc.reason}") from exc
        return json.loads(body) if body else {}

    # ------------------------------------------------------------------
    def ready(self) -> Dict[str, Any]:
        """健康检查。"""

        return self._request("GET", "/health/ready")

    def ensure_scope(self, scope_title: str, summary: str, idempotency_key: str) -> str:
        """创建 Scope（同一 idempotency_key 复用同一个 Scope），返回 scope_id。"""

        payload = {
            "title": scope_title,
            "summary": summary,
            "idempotency_key": idempotency_key,
        }
        result = self._request("POST", "/v1/scopes", payload)
        scope_id = result.get("scope_id")
        if not scope_id:
            raise PowerContextError(f"创建 Scope 未返回 scope_id：{result}")
        return str(scope_id)

    def remember(self, scope_id: str, kind: str, text: str) -> Dict[str, Any]:
        """写入一条记忆（显式写入，不需要模型参与）。"""

        return self._request(
            "POST",
            "/v1/memory/remember",
            {"scope_id": scope_id, "kind": kind, "text": text},
        )

    def list_memories(self, scope_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """列出 Scope 下的原子记忆条目（自动翻页）。"""

        items: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        while len(items) < limit:
            payload: Dict[str, Any] = {"scope_id": scope_id, "limit": min(50, limit - len(items))}
            if cursor:
                payload["cursor"] = cursor
            result = self._request("POST", "/v1/atomic-memory/list", payload)
            items.extend(result.get("items", []))
            cursor = result.get("next_cursor")
            if not cursor:
                break
        return items

    def search_memories(self, scope_id: str, query: str, limit: int = 50) -> Dict[str, Any]:
        """按查询检索记忆条目。"""

        return self._request(
            "POST",
            "/v1/memory/search",
            {"scope_id": scope_id, "query": query, "limit": limit},
        )

    def prepare_context(self, scope_id: str, query: str, max_bytes: int = 4000) -> Dict[str, Any]:
        """有界召回。"""

        return self._request(
            "POST",
            "/v1/context/prepare",
            {"scope_id": scope_id, "query": query, "max_bytes": max_bytes},
        )


def encode_state(task_id: str, kind: str, content: str) -> str:
    """把一条状态编码成记忆正文。"""

    return f"[{task_id}][{kind}] {content}"


def decode_states(task_id: str, items: List[Dict[str, Any]]) -> TaskState:
    """把记忆条目解析成任务状态（按 ``(类型, 内容)`` 去重并保留首次出现顺序）。"""

    state = TaskState(task_id=task_id, origin="powercontext")
    seen = set()
    for item in items:
        text = str(item.get("text") or "")
        match = _STATE_PATTERN.match(text)
        if not match:
            continue
        if match.group("task") != task_id:
            continue
        kind = match.group("kind").strip()
        content = match.group("content").strip()
        key = (kind, content)
        if key in seen:
            continue
        seen.add(key)
        if kind == "done":
            state.done.append(content)
        elif kind == "todo":
            state.todo.append(content)
        elif kind == "verification":
            state.verifications.append({"raw": content})
        elif kind == "note":
            state.notes.append(content)
    return state


def parse_verification(content: str) -> Dict[str, Any]:
    """解析验证结果文本。"""

    result: Dict[str, Any] = {"raw": content}
    for part in content.split("|"):
        key, _, value = part.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key in {"phase", "command", "exit_code", "passed", "failed", "log"}:
            if key in {"exit_code", "passed", "failed"}:
                try:
                    result[key] = int(value)
                except ValueError:
                    result[key] = value
            else:
                result[key] = value
    return result


def verification_text(
    phase: str,
    command: str,
    exit_code: int,
    passed: int,
    failed: int,
    log: str = "",
) -> str:
    """把验证结果编码成状态正文。"""

    return (
        f"phase={phase} | command={command} | exit_code={exit_code} | "
        f"passed={passed} | failed={failed} | log={log}"
    )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
