#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  端侧 AI 推理性能优化与 seekdb 混合检索 (阶跃星辰赛题)"
echo "  2026 OceanBase 数据库大赛 · PowerContext 生态"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo -e "\n[1/3] 检查 Node.js 运行环境..."
if ! command -v node &> /dev/null; then
    echo "错误: 未检测到 node 命令，请先安装 Node.js LTS (>= 18.0.0)。"
    exit 1
fi
echo "Node.js 版本: $(node -v)"

echo -e "\n[2/3] 检查依赖包..."
if [ ! -d "node_modules" ]; then
    echo "正在执行 npm install..."
    npm install
else
    echo "依赖已就绪。"
fi

echo -e "\n[3/3] 启动知识库应用服务..."
echo "访问地址: http://localhost:3000"
npm start
