"""sddctx 模块自身的单元测试。

覆盖：规格解析与版本化、关键词切分、上下文包组装、统一 diff 应用。
这些测试不依赖 seekdb / PowerContext，可在干净环境直接运行：

    python -m pytest minimax/tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sddctx.importer import _field, sha256_text  # noqa: E402
from sddctx.patcher import apply_unified_diff, make_unified_diff  # noqa: E402
from sddctx.retriever import tokenize  # noqa: E402


def test_field_parsing_reads_spec_metadata():
    body = "- 规格 ID：SPEC-ORD-003\n- 所属模块：order_fulfillment.filters\n"
    assert _field(body, "spec_id") == "SPEC-ORD-003"
    assert _field(body, "module") == "order_fulfillment.filters"
    assert _field(body, "status") == ""


def test_content_hash_changes_with_content():
    assert sha256_text("a") != sha256_text("b")
    assert sha256_text("a") == sha256_text("a")


def test_tokenize_keeps_identifiers_and_chinese_bigrams():
    tokens = tokenize("为订单查询增加 min_amount 金额区间筛选")
    assert "min_amount" in tokens
    assert any(token.startswith("订单") for token in tokens)
    assert "金额" in tokens


def test_unified_diff_round_trip(tmp_path):
    target = tmp_path / "sample.py"
    original = "def f():\n    return 1\n"
    target.write_text(original, encoding="utf-8")
    updated = "def f():\n    return 2\n"
    diff = make_unified_diff({"sample.py": original}, {"sample.py": updated})
    assert "diff --git a/sample.py b/sample.py" in diff

    result = apply_unified_diff(diff, tmp_path)
    assert result["changed_files"] == ["sample.py"]
    assert target.read_text(encoding="utf-8") == updated


def test_apply_diff_rejects_wrong_context(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("def f():\n    return 1\n", encoding="utf-8")
    diff = make_unified_diff(
        {"sample.py": "def f():\n    return 1\n"},
        {"sample.py": "def f():\n    return 2\n"},
    )
    target.write_text("def g():\n    return 3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        apply_unified_diff(diff, tmp_path)
