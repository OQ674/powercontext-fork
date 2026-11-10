"""召回器：基于 SQL 在 seekdb 中挑选与任务相关的规格、代码与测试。

召回分三路：

1. **规格**：关键词命中（标题 / 关键词 / 正文）→ 规格条目。
2. **代码**：规格声明的"关联代码"文件 + 符号名 / 签名命中 → 需要修改的文件与符号。
3. **测试**：规格声明的"关联测试"文件 + 用例名 / 用途命中 → 验证用例。

候选筛选在数据库中完成（真实 SQL 命中 ``LIKE`` 条件并给出 ``LIMIT``），
精确打分在模块内按命中的关键词数量计算；SQL 与命中结果都会写入
``sdd_retrieval_log``，全部 SQL 还会写入 ``sdd_query_log``。
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .db import Database
from .models import RetrievedItem

_CJK = re.compile(r"[\u4e00-\u9fff]+")
_ASCII = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PATH = re.compile(r"[\w./\\-]+\.py")

_STOPWORDS = {
    "the", "and", "for", "with", "add", "new", "test", "tests", "task", "code", "file",
    "function", "class", "module", "spec", "requirement",
}


def tokenize(text: str, limit: int = 14) -> List[str]:
    """把任务描述切成检索关键词。

    英文/标识符整体保留；中文按二元组切分，避免整句匹配不到。
    """

    tokens: List[str] = []
    for word in _ASCII.findall(text or ""):
        lowered = word.lower()
        if len(lowered) < 2 or lowered in _STOPWORDS:
            continue
        tokens.append(word)
    for run in _CJK.findall(text or ""):
        if len(run) == 1:
            tokens.append(run)
            continue
        for index in range(len(run) - 1):
            tokens.append(run[index : index + 2])
    unique: List[str] = []
    for token in sorted(dict.fromkeys(tokens), key=lambda item: (-len(item), item)):
        if token not in unique:
            unique.append(token)
        if len(unique) >= limit:
            break
    return unique


def _like(token: str) -> str:
    escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _conditions(tokens: Sequence[str], columns: Sequence[str]) -> Tuple[str, List[str]]:
    parts: List[str] = []
    params: List[str] = []
    for token in tokens:
        column_parts = []
        for column in columns:
            column_parts.append(f"{column} LIKE %s")
            params.append(_like(token))
        parts.append("(" + " OR ".join(column_parts) + ")")
    return " OR ".join(parts), params


class Retriever:
    """把任务描述映射到规格 / 代码 / 测试。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    # ------------------------------------------------------------------
    def retrieve_specs(
        self,
        task_text: str,
        task_id: str = "",
        limit: int = 6,
    ) -> List[RetrievedItem]:
        tokens = tokenize(task_text)
        if not tokens:
            return []
        where, params = _conditions(tokens, ("title", "keywords", "body", "module"))
        sql = f"""
            SELECT spec_id, title, module, status, body, keywords, related_code, related_tests,
                   source_file, content_hash, revision
              FROM sdd_spec_item
             WHERE {where}
             ORDER BY spec_id ASC
             LIMIT {int(limit)}
        """
        rows = self.database.query(sql, params)
        items: List[RetrievedItem] = []
        for row in rows:
            hits = self._hit_words(row, tokens)
            reasons = [f"关键词命中：{hits}", f"规格状态：{row['status']}"]
            if row.get("related_code"):
                reasons.append(f"规格声明的关联代码：{row['related_code']}")
            if row.get("related_tests"):
                reasons.append(f"规格声明的关联测试：{row['related_tests']}")
            items.append(
                RetrievedItem(
                    kind="spec",
                    ref=str(row["spec_id"]),
                    score=float(len(hits.split("、")) if hits else 1),
                    reasons=reasons,
                    payload=dict(row),
                )
            )
        items.sort(key=lambda item: (-item.score, item.ref))
        items = items[:limit]
        self._log_retrieval(task_id, task_text, "spec", items, sql)
        return items

    def _hit_words(self, row: Dict[str, object], tokens: Sequence[str]) -> str:
        haystack = " ".join(str(row.get(key) or "") for key in ("title", "keywords", "body"))
        hits = [token for token in tokens if token in haystack]
        return "、".join(hits[:6]) if hits else "任务描述"

    # ------------------------------------------------------------------
    def retrieve_code(
        self,
        task_text: str,
        spec_items: Sequence[RetrievedItem],
        task_id: str = "",
        limit: int = 12,
    ) -> List[RetrievedItem]:
        tokens = tokenize(task_text)
        referenced = self._referenced_paths(spec_items)
        params: List[str] = []
        clauses: List[str] = []
        if referenced:
            placeholders = ", ".join(["%s"] * len(referenced))
            clauses.append(f"file_path IN ({placeholders})")
            params.extend(referenced)
        if tokens:
            where, token_params = _conditions(tokens, ("symbol", "signature", "docstring"))
            clauses.append(f"({where})")
            params.extend(token_params)
        if not clauses:
            return []
        sql = f"""
            SELECT file_path, symbol, kind, signature, docstring, line_start, line_end,
                   source_file, content_hash
              FROM sdd_code_symbol
             WHERE {' OR '.join(clauses)}
             ORDER BY file_path ASC, line_start ASC
             LIMIT {int(limit)}
        """
        rows = self.database.query(sql, params)
        items: List[RetrievedItem] = []
        for row in rows:
            reasons: List[str] = []
            score = 0.0
            if row["file_path"] in referenced:
                reasons.append("被生效规格声明为关联代码")
                score += 5
            hits = [
                token
                for token in tokens
                if token in f"{row['symbol']} {row['signature']} {row['docstring']}"
            ]
            if hits:
                reasons.append(f"符号命中关键词：{'、'.join(hits[:4])}")
                score += len(hits)
            items.append(
                RetrievedItem(
                    kind="code",
                    ref=f"{row['file_path']}::{row['symbol']}",
                    score=score,
                    reasons=reasons or ["任务描述命中"],
                    payload=dict(row),
                )
            )
        items.sort(key=lambda item: (-item.score, item.ref))
        items = items[:limit]
        self._log_retrieval(task_id, task_text, "code", items, sql)
        return items

    # ------------------------------------------------------------------
    def retrieve_tests(
        self,
        task_text: str,
        spec_items: Sequence[RetrievedItem],
        code_items: Sequence[RetrievedItem],
        task_id: str = "",
        limit: int = 12,
    ) -> List[RetrievedItem]:
        tokens = tokenize(task_text)
        referenced = self._referenced_paths(spec_items, field="related_tests")
        code_files = sorted({str(item.payload.get("file_path")) for item in code_items})
        params: List[str] = []
        clauses: List[str] = []
        if referenced:
            placeholders = ", ".join(["%s"] * len(referenced))
            clauses.append(f"file_path IN ({placeholders})")
            params.extend(referenced)
        if code_files:
            placeholders = ", ".join(["%s"] * len(code_files))
            clauses.append(f"file_path IN ({placeholders})")
            params.extend(code_files)
        if tokens:
            where, token_params = _conditions(tokens, ("test_name", "purpose", "node_id"))
            clauses.append(f"({where})")
            params.extend(token_params)
        if not clauses:
            return []
        sql = f"""
            SELECT node_id, file_path, test_name, purpose, markers, source_file, content_hash
              FROM sdd_test_case
             WHERE {' OR '.join(clauses)}
             ORDER BY file_path ASC, node_id ASC
             LIMIT {int(limit)}
        """
        rows = self.database.query(sql, params)
        items: List[RetrievedItem] = []
        for row in rows:
            reasons: List[str] = []
            score = 0.0
            if row["file_path"] in referenced:
                reasons.append("被生效规格声明为关联测试")
                score += 5
            if row["file_path"] in code_files:
                reasons.append("与待修改代码同属一个测试文件")
                score += 1
            hits = [
                token
                for token in tokens
                if token in f"{row['test_name']} {row['purpose']}"
            ]
            if hits:
                reasons.append(f"用例命中关键词：{'、'.join(hits[:4])}")
                score += len(hits)
            items.append(
                RetrievedItem(
                    kind="test",
                    ref=str(row["node_id"]),
                    score=score,
                    reasons=reasons or ["任务描述命中"],
                    payload=dict(row),
                )
            )
        items.sort(key=lambda item: (-item.score, item.ref))
        items = items[:limit]
        self._log_retrieval(task_id, task_text, "test", items, sql)
        return items

    # ------------------------------------------------------------------
    def _referenced_paths(
        self,
        spec_items: Iterable[RetrievedItem],
        field: str = "related_code",
    ) -> List[str]:
        paths: List[str] = []
        for item in spec_items:
            raw = str(item.payload.get(field) or "")
            for match in _PATH.findall(raw):
                normalized = match.replace("\\", "/")
                if normalized not in paths:
                    paths.append(normalized)
        return paths

    def _log_retrieval(
        self,
        task_id: str,
        task_text: str,
        target_kind: str,
        items: Sequence[RetrievedItem],
        sql: str,
    ) -> None:
        if not items:
            return
        rows = [
            (
                task_id[:64],
                task_text[:500],
                target_kind,
                item.ref[:500],
                float(item.score),
                " ".join(sql.split())[:4000],
            )
            for item in items
        ]
        self.database.executemany(
            "INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, NOW())",
            rows,
        )
