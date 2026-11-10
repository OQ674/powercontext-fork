"""领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SpecItem:
    """一条规格。"""

    spec_id: str
    title: str
    module: str = ""
    status: str = "生效"
    body: str = ""
    keywords: str = ""
    related_code: str = ""
    related_tests: str = ""
    source_file: str = ""
    content_hash: str = ""
    revision: int = 1
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "title": self.title,
            "module": self.module,
            "status": self.status,
            "body": self.body,
            "keywords": self.keywords,
            "related_code": self.related_code,
            "related_tests": self.related_tests,
            "source_file": self.source_file,
            "content_hash": self.content_hash,
            "revision": self.revision,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class CodeSymbol:
    """一个代码符号。"""

    file_path: str
    symbol: str
    kind: str
    signature: str = ""
    docstring: str = ""
    line_start: int = 0
    line_end: int = 0
    source_file: str = ""
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "symbol": self.symbol,
            "kind": self.kind,
            "signature": self.signature,
            "docstring": self.docstring,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "source_file": self.source_file,
            "content_hash": self.content_hash,
        }


@dataclass
class TestCase:
    """一个测试用例。"""

    node_id: str
    file_path: str
    test_name: str
    purpose: str = ""
    markers: str = ""
    source_file: str = ""
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "file_path": self.file_path,
            "test_name": self.test_name,
            "purpose": self.purpose,
            "markers": self.markers,
            "source_file": self.source_file,
            "content_hash": self.content_hash,
        }


@dataclass
class RetrievedItem:
    """召回结果，附带来源与命中理由。"""

    kind: str
    ref: str
    score: float
    reasons: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskState:
    """任务状态快照。"""

    task_id: str
    title: str = ""
    description: str = ""
    status: str = "in_progress"
    done: List[str] = field(default_factory=list)
    todo: List[str] = field(default_factory=list)
    verifications: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    origin: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "done": list(self.done),
            "todo": list(self.todo),
            "verifications": list(self.verifications),
            "notes": list(self.notes),
            "origin": self.origin,
        }
