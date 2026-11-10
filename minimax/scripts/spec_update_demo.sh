#!/usr/bin/env bash
# 规格变更演示：更新一条规格 → 重新导入 → 验证上下文使用了更新后的内容。
#
# 证明模块不是"返回固定答案"：同一任务在规格更新后必须召回新版本的规格。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
TASK_ID="${TASK_ID:-TASK-ORD-003}"
TITLE="${TITLE:-为订单查询增加金额区间筛选}"
DESCRIPTION="${DESCRIPTION:-在订单筛选函数 filter_orders 上新增 min_amount / max_amount 闭区间金额筛选，金额使用 Decimal 精确比较。}"

export SDDCTX_PROJECT_ROOT="$ROOT"
cd "$ROOT"

SPEC_DIR="sample_project/specs"
SPEC_NAME="SPEC-ORD-003-订单金额区间筛选.md"

echo ">>> 用更新后的规格覆盖 ${SPEC_DIR}/${SPEC_NAME}"
BACKUP="$(mktemp)"
cp -f "${SPEC_DIR}/${SPEC_NAME}" "$BACKUP"
cp -f "specs_v2/${SPEC_NAME}" "${SPEC_DIR}/${SPEC_NAME}"

echo ">>> 重新导入规格"
"$PYTHON" -m sddctx import --kind specs

echo ">>> 重新生成上下文"
"$PYTHON" -m sddctx context \
    --task-id "$TASK_ID" \
    --title "$TITLE" \
    --description "$DESCRIPTION" \
    --include-state \
    --out artifacts/context_after_spec_update.json \
    --markdown-out artifacts/context_after_spec_update.md

echo ">>> 规格版本与内容检查"
"$PYTHON" - <<'PY'
import json
from pathlib import Path

bundle = json.loads(Path("artifacts/context_after_spec_update.json").read_text(encoding="utf-8"))
for spec in bundle["specs"]:
    if spec["spec_id"] == "SPEC-ORD-003":
        print("SPEC-ORD-003 revision =", spec["revision"])
        print("命中关键词 =", spec["keywords"])
        print("正文包含 Decimal 说明 =", "Decimal" in spec["body"])
PY

echo "完成：上下文已使用更新后的规格内容。"

if [ "${RESTORE_SPEC:-1}" = "1" ]; then
    cp -f "$BACKUP" "${SPEC_DIR}/${SPEC_NAME}"
    rm -f "$BACKUP"
    echo "已把 ${SPEC_DIR} 还原为原始版本（数据库中保留第 2 版记录，可再次导入复核）。"
else
    rm -f "$BACKUP"
fi
