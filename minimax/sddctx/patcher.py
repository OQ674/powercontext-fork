"""统一 diff 应用器。

不依赖 git / patch 命令，保证在任意环境（含 Windows、嵌入式数据库演示机）
都能把 MiniMax 生成的补丁可靠地应用到工作区，并生成应用后的统一 diff。
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_FILE_HEADER = re.compile(r"^diff --git a/(?P<old>.+?) b/(?P<new>.+)$")


def _parse_sections(text: str) -> List[Tuple[str, str, List[str]]]:
    """把 diff 文本拆成 ``(旧路径, 新路径, 原始行)``。"""

    sections: List[Tuple[str, str, List[str]]] = []
    current_old: Optional[str] = None
    current_new: Optional[str] = None
    lines: List[str] = []
    for line in text.splitlines():
        header = _FILE_HEADER.match(line)
        if header:
            if current_old is not None:
                sections.append((current_old, current_new or current_old, lines))
            current_old = header.group("old")
            current_new = header.group("new")
            lines = []
            continue
        if line.startswith("diff --git"):
            continue
        lines.append(line)
    if current_old is not None:
        sections.append((current_old, current_new or current_old, lines))
    return sections


def _apply_hunks(original: List[str], hunks: List[List[str]]) -> List[str]:
    result = list(original)
    offset = 0
    for hunk in hunks:
        match = _HUNK.match(hunk[0])
        if not match:
            raise ValueError(f"无法解析 hunk 头：{hunk[0]}")
        old_start = int(match.group(1))
        old_side: List[str] = []   # 补丁前的原始内容（上下文 + 删除行）
        new_side: List[str] = []   # 补丁后的新内容（上下文 + 新增行）
        for line in hunk[1:]:
            if line.startswith(" "):
                old_side.append(line[1:])
                new_side.append(line[1:])
            elif line.startswith("-"):
                old_side.append(line[1:])
            elif line.startswith("+"):
                new_side.append(line[1:])
            elif line.startswith("\\"):
                continue
        index = old_start - 1 + offset
        if result[index : index + len(old_side)] != old_side:
            # 上下文不匹配时退化为按内容搜索
            found = -1
            for candidate in range(0, len(result) - len(old_side) + 1):
                if result[candidate : candidate + len(old_side)] == old_side:
                    found = candidate
                    break
            if found < 0:
                raise ValueError(f"补丁上下文不匹配（第 {old_start} 行附近）")
            index = found
        result[index : index + len(old_side)] = new_side
        offset += len(new_side) - len(old_side)
    return result


def _hunk_markers(hunk: List[str]) -> Tuple[List[str], List[str]]:
    """返回 hunk 的新增行与删除行。"""

    added: List[str] = []
    removed: List[str] = []
    for line in hunk[1:]:
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def _contains_in_order(needle: List[str], haystack: List[str]) -> bool:
    """判断 needle 是否按顺序出现在 haystack 中。"""

    if not needle:
        return True
    index = 0
    for line in haystack:
        if line == needle[index]:
            index += 1
            if index == len(needle):
                return True
    return False


def patch_status(diff_text: str, root: Path) -> Dict[str, object]:
    """判断补丁是否已经应用到工作区。

    返回 ``{"applied": bool, "already_applied": bool, "files": {...}}``。
    """

    files: Dict[str, Dict[str, bool]] = {}
    all_applied = True
    any_file_exists = False
    for old_path, new_path, raw_lines in _parse_sections(diff_text):
        hunks: List[List[str]] = []
        current: Optional[List[str]] = None
        for line in raw_lines:
            if line.startswith("@@"):
                current = [line]
                hunks.append(current)
            elif current is not None:
                current.append(line)
        target = root / new_path
        content = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
        file_applied = bool(content) and all(
            _contains_in_order(_hunk_markers(hunk)[0], content) for hunk in hunks
        )
        files[new_path] = {"exists": target.exists(), "applied": file_applied}
        any_file_exists = any_file_exists or target.exists()
        all_applied = all_applied and file_applied
    return {
        "applied": all_applied and any_file_exists,
        "already_applied": all_applied and any_file_exists,
        "files": files,
    }


def apply_unified_diff(diff_text: str, root: Path, *, dry_run: bool = False) -> Dict[str, object]:
    """把统一 diff 应用到 ``root`` 目录下的文件。

    如果补丁已经应用过，则跳过（不报错），方便重复执行验证样例。
    """

    changed: List[str] = []
    skipped: List[str] = []
    details: List[Dict[str, object]] = []
    for old_path, new_path, raw_lines in _parse_sections(diff_text):
        hunks: List[List[str]] = []
        current: Optional[List[str]] = None
        for line in raw_lines:
            if line.startswith("@@"):
                current = [line]
                hunks.append(current)
            elif current is not None:
                current.append(line)
        target = root / new_path
        if not target.exists():
            raise FileNotFoundError(f"补丁目标文件不存在：{target}")
        original_text = target.read_text(encoding="utf-8")
        original_lines = original_text.splitlines()
        already = bool(original_lines) and all(
            _contains_in_order(_hunk_markers(hunk)[0], original_lines) for hunk in hunks
        )
        if already:
            skipped.append(new_path)
            details.append({"path": new_path, "old_path": old_path, "added": 0, "removed": 0, "skipped": True})
            continue
        updated_lines = _apply_hunks(original_lines, hunks)
        updated_text = "\n".join(updated_lines)
        if original_text.endswith("\n"):
            updated_text += "\n"
        if not dry_run:
            target.write_text(updated_text, encoding="utf-8")
        changed.append(new_path)
        details.append(
            {
                "path": new_path,
                "old_path": old_path,
                "added": max(0, len(updated_lines) - len(original_lines)),
                "removed": max(0, len(original_lines) - len(updated_lines)),
                "skipped": False,
            }
        )
    return {"changed_files": changed, "skipped_files": skipped, "details": details}


def make_unified_diff(before: Dict[str, str], after: Dict[str, str]) -> str:
    """根据修改前后的文件内容生成统一 diff。"""

    chunks: List[str] = []
    for path in sorted(set(before) | set(after)):
        old_lines = before.get(path, "").splitlines()
        new_lines = after.get(path, "").splitlines()
        if old_lines == new_lines:
            continue
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
            n=3,
        )
        body = "\n".join(diff)
        chunks.append(f"diff --git a/{path} b/{path}\n{body}")
    return "\n".join(chunks) + ("\n" if chunks else "")
