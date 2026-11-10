"""导入器：把规格、代码符号、测试用例写入 seekdb。

导入具备幂等与版本化特性：

* 同一 ``spec_id`` 再次导入时，若内容哈希未变则不产生新版本；
* 内容变化时 ``revision`` 自增，``body``/``content_hash`` 更新，
  因此"更新规格并重新导入"后模块一定读到新内容，而不是固定答案。
"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .db import Database

_FIELD_PATTERNS = {
    "spec_id": re.compile(r"规格\s*ID[：:]\s*(\S+)"),
    "module": re.compile(r"所属模块[：:]\s*(\S+)"),
    "status": re.compile(r"状态[：:]\s*(\S+)"),
    "keywords": re.compile(r"关键词[：:]\s*(.+)"),
    "related_code": re.compile(r"关联代码[：:]\s*(.+)"),
    "related_tests": re.compile(r"关联测试[：:]\s*(.+)"),
}

_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".sddctx", ".pytest_cache"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _field(body: str, name: str) -> str:
    match = _FIELD_PATTERNS[name].search(body)
    return match.group(1).strip() if match else ""


# ----------------------------------------------------------------------
# 规格
# ----------------------------------------------------------------------
def import_specs(database: Database, specs_dir: Path, project_root: Optional[Path] = None) -> Dict[str, object]:
    """导入规格目录下的 Markdown 规格文档。"""

    specs_dir = Path(specs_dir)
    project_root = Path(project_root) if project_root else specs_dir.parent
    imported: List[str] = []
    updated: List[str] = []
    unchanged: List[str] = []

    for path in sorted(specs_dir.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        spec_id = _field(body, "spec_id") or path.stem
        content_hash = sha256_text(body)
        source_file = _relative(path, project_root)

        row = database.query_one(
            "SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s",
            (spec_id,),
        )
        if row is None:
            database.execute(
                """
                INSERT INTO sdd_spec_item
                    (spec_id, title, module, status, body, keywords, related_code, related_tests,
                     source_file, content_hash, revision, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
                """,
                (
                    spec_id,
                    title,
                    _field(body, "module"),
                    _field(body, "status") or "生效",
                    body,
                    _field(body, "keywords"),
                    _field(body, "related_code"),
                    _field(body, "related_tests"),
                    source_file,
                    content_hash,
                ),
            )
            imported.append(spec_id)
        elif row["content_hash"] != content_hash:
            database.execute(
                """
                UPDATE sdd_spec_item
                   SET title = %s, module = %s, status = %s, body = %s, keywords = %s,
                       related_code = %s, related_tests = %s, source_file = %s,
                       content_hash = %s, revision = revision + 1, updated_at = NOW()
                 WHERE spec_id = %s
                """,
                (
                    title,
                    _field(body, "module"),
                    _field(body, "status") or "生效",
                    body,
                    _field(body, "keywords"),
                    _field(body, "related_code"),
                    _field(body, "related_tests"),
                    source_file,
                    content_hash,
                    spec_id,
                ),
            )
            updated.append(spec_id)
        else:
            unchanged.append(spec_id)

    return {
        "specs_dir": str(specs_dir),
        "imported": imported,
        "updated": updated,
        "unchanged": unchanged,
        "total": len(imported) + len(updated) + len(unchanged),
    }


# ----------------------------------------------------------------------
# 代码
# ----------------------------------------------------------------------
def _iter_python_files(root: Path, skip_dirs: Tuple[str, ...] = ()) -> List[Path]:
    files: List[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS or part in skip_dirs for part in path.parts):
            continue
        files.append(path)
    return files


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def import_code(database: Database, root: Path, skip_dirs: Tuple[str, ...] = ("tests",)) -> Dict[str, object]:
    """导入工程代码中的模块、类、函数与方法。"""

    root = Path(root)
    symbols = 0
    files = 0

    for path in _iter_python_files(root, skip_dirs=skip_dirs):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:  # pragma: no cover - 语法错误时跳过并记录
            print(f"[sddctx] 跳过无法解析的文件 {path}: {exc}")
            continue

        file_hash = sha256_text(source)
        source_file = _relative(path, root)
        lines = source.splitlines()

        for node, inside_class in _walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if inside_class else "function"
                signature = _signature(node)
                docstring = ast.get_docstring(node) or ""
                block = "\n".join(lines[node.lineno - 1 : node.end_lineno or node.lineno])
                database.execute(
                    """
                    INSERT INTO sdd_code_symbol
                        (file_path, symbol, kind, signature, docstring, line_start, line_end,
                         source_file, content_hash, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        signature = VALUES(signature), docstring = VALUES(docstring),
                        line_end = VALUES(line_end), content_hash = VALUES(content_hash),
                        updated_at = NOW()
                    """,
                    (
                        source_file,
                        node.name,
                        kind,
                        signature,
                        docstring,
                        node.lineno,
                        node.end_lineno or node.lineno,
                        source_file,
                        sha256_text(block),
                    ),
                )
                symbols += 1
            elif isinstance(node, ast.ClassDef):
                database.execute(
                    """
                    INSERT INTO sdd_code_symbol
                        (file_path, symbol, kind, signature, docstring, line_start, line_end,
                         source_file, content_hash, updated_at)
                    VALUES (%s, %s, 'class', %s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        signature = VALUES(signature), docstring = VALUES(docstring),
                        line_end = VALUES(line_end), content_hash = VALUES(content_hash),
                        updated_at = NOW()
                    """,
                    (
                        source_file,
                        node.name,
                        f"class {node.name}:",
                        ast.get_docstring(node) or "",
                        node.lineno,
                        node.end_lineno or node.lineno,
                        source_file,
                        file_hash,
                    ),
                )
                symbols += 1
        files += 1

    return {"files": files, "symbols": symbols, "root": str(root)}


def _walk(tree: ast.AST):
    """遍历 AST，同时标记节点是否位于类体内。"""

    def visit(node: ast.AST, inside_class: bool):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield child, inside_class
                yield from visit(child, True)
            else:
                yield child, inside_class
                yield from visit(child, inside_class)

    yield from visit(tree, False)


def _signature(node) -> str:
    try:
        text = ast.unparse(node)
    except Exception:  # pragma: no cover
        text = f"def {node.name}(...)"
    head = text.split("\n", 1)[0].strip()
    return head


# ----------------------------------------------------------------------
# 测试
# ----------------------------------------------------------------------
def import_tests(database: Database, root: Path, tests_dir: str = "tests") -> Dict[str, object]:
    """导入 pytest 测试用例（node id 级别）。"""

    root = Path(root)
    tests_root = root / tests_dir
    if not tests_root.exists():
        tests_root = root

    count = 0
    files = 0
    for path in _iter_python_files(tests_root):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover
            continue
        file_path = _relative(path, root)
        source_file = file_path
        file_hash = sha256_text(source)
        lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            markers = ",".join(sorted({_marker_name(dec) for dec in node.decorator_list}))
            purpose = (ast.get_docstring(node) or "").strip().split("\n")[0]
            block = "\n".join(lines[node.lineno - 1 : node.end_lineno or node.lineno])
            node_id = f"{file_path}::{node.name}"
            database.execute(
                """
                INSERT INTO sdd_test_case
                    (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    purpose = VALUES(purpose), markers = VALUES(markers),
                    content_hash = VALUES(content_hash), updated_at = NOW()
                """,
                (
                    node_id,
                    file_path,
                    node.name,
                    purpose,
                    markers,
                    source_file,
                    sha256_text(block) if block else file_hash,
                ),
            )
            count += 1
        files += 1

    return {"files": files, "tests": count, "root": str(tests_root)}


def _marker_name(decorator: ast.AST) -> str:
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    if isinstance(decorator, ast.Name):
        return decorator.id
    return "marker"
