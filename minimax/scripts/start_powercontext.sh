#!/usr/bin/env bash
# 启动 PowerContext Server（本地 SQLite 存储，不需要任何模型 API）。
#
# 用法：
#   bash scripts/start_powercontext.sh          # 前台启动
#   POWERCONTEXT_PORT=8010 bash scripts/start_powercontext.sh
#
# 生成的环境文件：.sddctx/powercontext/.env（包含绝对路径，不提交真实凭据）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${POWERCONTEXT_PORT:-8000}"
HOST="${POWERCONTEXT_HOST:-127.0.0.1}"
DATA_DIR="${POWERCONTEXT_DATA_DIR:-$ROOT/.sddctx/powercontext}"
ENV_FILE="${POWERCONTEXT_ENV_FILE:-$DATA_DIR/.env}"
POWERCONTEXT_BIN="${POWERCONTEXT_BIN:-powercontext}"

mkdir -p "$DATA_DIR"
cat > "$ENV_FILE" <<EOF
# 由 scripts/start_powercontext.sh 生成（PowerContext 1.5.1，Basic memory 模式）
POWERCONTEXT_SERVER_HTTP_HOST=$HOST
POWERCONTEXT_SERVER_HTTP_PORT=$PORT
POWERCONTEXT_SERVER_ACCESS_MODE=disabled
POWERCONTEXT_SERVER_DATABASE_KIND=sqlite
POWERCONTEXT_SERVER_DATABASE_URL=sqlite+aiosqlite:///$DATA_DIR/powercontext.db
POWERCONTEXT_HOME=$DATA_DIR
EOF

echo "PowerContext 环境文件：$ENV_FILE"
echo "数据库：$DATA_DIR/powercontext.db"
exec "$POWERCONTEXT_BIN" server run --env-file "$ENV_FILE"
