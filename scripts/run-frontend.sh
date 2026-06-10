#!/bin/bash

# CircuitGPT 前端启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "================================"
echo "启动 CircuitGPT 前端服务"
echo "================================"

# 检查前端目录
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "错误: 前端目录不存在: $FRONTEND_DIR"
    exit 1
fi

cd "$FRONTEND_DIR"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "首次运行，正在安装依赖..."
    npm install
fi

# 检查 .env.local
if [ ! -f ".env.local" ]; then
    echo "警告: .env.local 文件不存在"
    if [ -f ".env.local.example" ]; then
        echo "正在从示例创建 .env.local..."
        cp .env.local.example .env.local
        echo "已创建 .env.local，请检查配置是否正确"
    fi
fi

echo ""
echo "启动开发服务器..."
echo "访问地址: http://localhost:3000"
echo ""

# 启动开发服务器
npm run dev
