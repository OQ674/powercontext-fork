#!/usr/bin/env bash
# 验证样例一键脚本（Linux / macOS）。
#
# 流程：还原到修改前 → 建库 → 导入规格/代码/测试 → 生成上下文 → 修改前跑目标功能测试 →
#       MiniMax 补丁落盘并应用 → 修改后跑全部测试 → 保存任务状态到 PowerContext →
#       重新启动模块读取并使用状态 → 导出数据库证据。
#
# 用法：
#   bash scripts/run_demo.sh
#   TASK_ID=TASK-ORD-XXX PYTHON=python3.12 bash scripts/run_demo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_ID="${TASK_ID:-TASK-ORD-003}"
TITLE="${TITLE:-为订单查询增加金额区间筛选}"
DESCRIPTION="${DESCRIPTION:-在订单筛选函数 filter_orders 上新增 min_amount / max_amount 闭区间金额筛选，金额使用 Decimal 精确比较；必须保持既有状态筛选、排序与分页行为不变，并让新增的目标功能测试通过。}"
PYTHON="${PYTHON:-python3}"

export SDDCTX_PROJECT_ROOT="$ROOT"
cd "$ROOT"

step() {
    echo ""
    echo "=============================================================="
    echo ">>> $*"
    echo "=============================================================="
}

step "0/9 把业务工程恢复到修改前状态（便于从零复现整个流程）"
bash scripts/reset_demo.sh

step "1/9 初始化数据库表结构（seekdb / OceanBase）"
"$PYTHON" -m sddctx db-init

step "2/9 导入规格、代码与测试"
"$PYTHON" -m sddctx import --kind all

step "3/9 根据任务生成开发上下文"
"$PYTHON" -m sddctx context \
    --task-id "$TASK_ID" \
    --title "$TITLE" \
    --description "$DESCRIPTION" \
    --include-state \
    --out artifacts/context_before.json \
    --markdown-out artifacts/context_before.md

step "4/9 修改前执行目标功能测试（预期失败：目标行为尚未实现）"
set +e
"$PYTHON" -m sddctx verify \
    --task-id "$TASK_ID" \
    --phase before \
    --target tests/test_feature_amount_filter.py \
    --log logs/pytest_before_feature.log
BEFORE_EXIT=$?
set -e
echo "修改前目标功能测试退出码：${BEFORE_EXIT}（非 0 表示目标行为尚未实现，符合预期）"

step "5/9 MiniMax 生成补丁并应用到业务工程"
"$PYTHON" -m sddctx agent-patch \
    --task-id "$TASK_ID" \
    --context artifacts/context_before.json \
    --patch-file artifacts/minimax_patch.diff \
    --apply

step "6/9 修改后执行目标功能测试与回归测试（预期全部通过）"
"$PYTHON" -m sddctx verify \
    --task-id "$TASK_ID" \
    --phase after-feature \
    --target tests/test_feature_amount_filter.py \
    --log logs/pytest_after_feature.log
"$PYTHON" -m sddctx verify \
    --task-id "$TASK_ID" \
    --phase after \
    --target tests \
    --log logs/pytest_after.log

step "7/9 保存任务状态到 PowerContext"
PASSED_COUNT="$(grep -oE '[0-9]+ passed' logs/pytest_after.log | tail -1 | grep -oE '[0-9]+' || true)"
FAILED_COUNT="$(grep -oE '[0-9]+ failed' logs/pytest_after.log | tail -1 | grep -oE '[0-9]+' || true)"
"$PYTHON" -m sddctx state-save \
    --task-id "$TASK_ID" \
    --done "导入 5 条规格到 seekdb（规格 / 代码符号 / 测试用例）" \
    --done "完成 ${TITLE}" \
    --done "在 seekdb 中建立规格/代码/测试索引并完成三路召回" \
    --done "由 MiniMax 生成补丁并应用到 filter_orders 与 HTTP 查询接口" \
    --todo "为金额区间筛选补充边界用例" \
    --note "上下文选择方式：规格声明的关联代码/关联测试优先，关键词命中作为补充" \
    --verification "phase=after | command=python -m pytest -q tests | exit_code=0 | passed=${PASSED_COUNT:-0} | failed=${FAILED_COUNT:-0} | log=logs/pytest_after.log"

step "8/9 重新启动模块，读取并使用已保存的任务状态"
"$PYTHON" -m sddctx state-show --task-id "$TASK_ID"
"$PYTHON" -m sddctx state-log --task-id "$TASK_ID" --out artifacts/powercontext_state_log.md
"$PYTHON" -m sddctx context \
    --task-id "$TASK_ID" \
    --title "$TITLE" \
    --description "$DESCRIPTION" \
    --include-state \
    --out artifacts/context_after.json \
    --markdown-out artifacts/context_after.md

step "9/9 导出数据库查询与检索证据"
"$PYTHON" -m sddctx evidence --out logs/db_query_log.md

echo ""
echo "验证样例执行完成。产物："
echo "  artifacts/context_before.json / context_after.json  上下文包（含真实来源）"
echo "  artifacts/minimax_patch.diff                        MiniMax 生成的代码差异"
echo "  artifacts/minimax_dev_log.jsonl                     MiniMax 开发记录"
echo "  logs/pytest_before_feature.log / pytest_after.log   修改前后测试日志"
echo "  logs/db_query_log.md                                seekdb 查询与检索记录"
