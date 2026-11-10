"""任务状态管理：本地镜像 + PowerContext。

状态写入两处：

* ``sdd_task_progress``（seekdb）—— 本地镜像，便于离线排查；
* PowerContext ``/v1/memory/remember`` —— 权威副本，跨进程、跨会话复用。

读取时**优先**使用 PowerContext；PowerContext 不可用时回退到本地镜像。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .config import Config
from .db import Database
from .models import TaskState
from .powercontext_client import (
    PowerContextClient,
    PowerContextError,
    decode_states,
    encode_state,
    parse_verification,
)

STATE_KINDS = ("done", "todo", "verification", "note")


class TaskStateStore:
    """任务状态存储。"""

    def __init__(
        self,
        database: Database,
        config: Config,
        client: Optional[PowerContextClient] = None,
    ) -> None:
        self.database = database
        self.config = config
        self.client = client

    # ------------------------------------------------------------------
    def scope_id(self) -> Optional[str]:
        """获取（必要时创建）PowerContext Scope。"""

        if self.client is None:
            return None
        try:
            return self.client.ensure_scope(
                scope_title=self.config.powercontext_scope,
                summary="SDD 上下文模块：任务状态与验证结果",
                idempotency_key=f"sddctx-{self.config.powercontext_scope}",
            )
        except PowerContextError:
            return None

    # ------------------------------------------------------------------
    def _existing_texts(self, task_id: str, scope_id: Optional[str]) -> set:
        """收集已存在的状态条目正文（PowerContext + 本地镜像），用于写入去重。"""

        existing = set()

        if scope_id and self.client is not None:
            try:
                for item in self.client.list_memories(scope_id):
                    text = str(item.get("text") or "").strip()
                    if text:
                        existing.add(text)
            except PowerContextError:
                pass

        try:
            rows = self.database.query(
                "SELECT kind, content FROM sdd_task_progress WHERE task_id = %s",
                (task_id,),
            )
        except Exception:  # pragma: no cover - 镜像表不可用时不影响主流程
            rows = []
        for row in rows:
            existing.add(encode_state(task_id, row["kind"], row["content"]).strip())

        return existing

    # ------------------------------------------------------------------
    def save(self, task_id: str, entries: Sequence[Tuple[str, str]]) -> Dict[str, object]:
        """写入状态条目（幂等）。

        ``entries`` 形如 ``[("done", "导入规格 5 条"), ("todo", "实现金额筛选")]``。

        同一 ``[任务ID][类型] 内容`` 已存在时跳过，避免重复运行累积重复条目。
        """

        scope_id = self.scope_id()
        existing = self._existing_texts(task_id, scope_id)
        written: List[str] = []
        skipped: List[str] = []
        for kind, content in entries:
            if kind not in STATE_KINDS:
                raise ValueError(f"未知的状态类型：{kind}")
            text = encode_state(task_id, kind, content)
            if text in existing:
                skipped.append(f"[{kind}] {content}")
                continue
            self.database.execute(
                "INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at)"
                " VALUES (%s, %s, %s, %s, NOW())",
                (task_id, kind, content, "local+powercontext" if scope_id else "local"),
            )
            if scope_id and self.client is not None:
                self.client.remember(scope_id, "sdd-task-state", text)
            existing.add(text)
            written.append(f"[{kind}] {content}")
        return {
            "task_id": task_id,
            "scope_id": scope_id,
            "written": written,
            "skipped": skipped,
            "powercontext": bool(scope_id),
        }

    # ------------------------------------------------------------------
    def load(self, task_id: str) -> TaskState:
        """读取任务状态（优先 PowerContext）。"""

        scope_id = self.scope_id()
        if scope_id and self.client is not None:
            try:
                items = self.client.list_memories(scope_id)
                state = decode_states(task_id, items)
                state.origin = f"powercontext:{scope_id}"
                if state.done or state.todo or state.verifications or state.notes:
                    state.verifications = [parse_verification(item["raw"]) for item in state.verifications]
                    return state
                return state
            except PowerContextError:
                pass

        rows = self.database.query(
            "SELECT kind, content FROM sdd_task_progress WHERE task_id = %s ORDER BY id ASC",
            (task_id,),
        )
        state = TaskState(task_id=task_id, origin="seekdb:sdd_task_progress")
        seen = set()
        for row in rows:
            kind = row["kind"]
            content = row["content"]
            key = (kind, content)
            if key in seen:
                continue
            seen.add(key)
            if kind == "done":
                state.done.append(content)
            elif kind == "todo":
                state.todo.append(content)
            elif kind == "verification":
                state.verifications.append(parse_verification(content))
            elif kind == "note":
                state.notes.append(content)
        return state
