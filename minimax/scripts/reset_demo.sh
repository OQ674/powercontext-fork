#!/usr/bin/env bash
# 把业务工程恢复到"修改前"状态，用于重新执行验证样例。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT="$ROOT/artifacts/before_snapshot"

echo "恢复业务工程到修改前状态 ..."
cp -f "$SNAPSHOT/src/order_fulfillment/filters.py" "$ROOT/sample_project/src/order_fulfillment/filters.py"
cp -f "$SNAPSHOT/src/order_fulfillment/service.py" "$ROOT/sample_project/src/order_fulfillment/service.py"
echo "已恢复：sample_project/src/order_fulfillment/{filters.py,service.py}"

if [ "${RESET_DB:-0}" = "1" ]; then
    echo "清空本地 seekdb 数据目录 ..."
    rm -rf "$ROOT/.sddctx/seekdb"
    echo "已清空：.sddctx/seekdb"
fi

if [ "${RESET_POWERCONTEXT:-0}" = "1" ]; then
    echo "提示：如需清空 PowerContext 状态，请删除 PowerContext 的 SQLite 数据文件后重启服务。"
fi

echo "完成。"
