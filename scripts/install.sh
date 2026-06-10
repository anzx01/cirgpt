#!/bin/bash

# CircuitGPT 一键安装脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "CircuitGPT 一键安装"
echo "========================================"

# 检查 Node.js
echo ""
echo "检查 Node.js..."
if ! command -v node &> /dev/null; then
    echo "错误: 未安装 Node.js"
    echo "请从 https://nodejs.org/ 下载并安装"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "警告: Node.js 版本过低 (当前: $(node --version), 需要: v18+)"
    echo "建议升级到 Node.js 18 或更高版本"
fi

echo "✓ Node.js $(node --version)"

# 检查 Python
echo ""
echo "检查 Python..."
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "错误: 未安装 Python"
    echo "请从 https://www.python.org/ 下载并安装"
    exit 1
fi

PYTHON_CMD="python"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
fi

echo "✓ Python $($PYTHON_CMD --version)"

# 安装前端依赖
echo ""
echo "========================================"
echo "安装前端依赖..."
echo "========================================"
cd "$PROJECT_ROOT/frontend"

if [ -d "node_modules" ]; then
    echo "node_modules 已存在，跳过安装"
else
    echo "正在安装前端依赖（可能需要几分钟）..."
    npm install || {
        echo "npm install 失败，尝试使用 --legacy-peer-deps..."
        npm install --legacy-peer-deps
    }
    echo "✓ 前端依赖安装完成"
fi

# 检查前端配置
if [ ! -f ".env.local" ]; then
    echo ""
    echo "创建前端配置文件..."
    if [ -f ".env.local.example" ]; then
        cp .env.local.example .env.local
        echo "✓ 已创建 .env.local"
    else
        echo "⚠ 未找到 .env.local.example，请手动创建 .env.local"
    fi
fi

# 配置后端
echo ""
echo "========================================"
echo "配置后端..."
echo "========================================"
cd "$PROJECT_ROOT/backend"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建 Python 虚拟环境..."
    $PYTHON_CMD -m venv venv
    echo "✓ 虚拟环境创建完成"
fi

# 检查后端配置
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠ 重要: 需要配置后端环境变量"
    echo ""
    echo "生成安全的 SECRET_KEY:"
    $PYTHON_CMD -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
    echo ""
    echo "请执行以下步骤:"
    echo "1. 复制上面生成的 SECRET_KEY"
    echo "2. 运行: cp .env.example .env"
    echo "3. 编辑 .env 文件，粘贴 SECRET_KEY"
    echo ""
    echo "或者运行: ./scripts/setup-backend.sh"
fi

echo ""
echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "下一步:"
echo "1. 配置后端 SECRET_KEY (如果尚未配置)"
echo "   cd backend"
echo "   python -c 'import secrets; print(secrets.token_urlsafe(32))'"
echo "   cp .env.example .env"
echo "   # 编辑 .env，填入生成的 SECRET_KEY"
echo ""
echo "2. 启动服务:"
echo "   ./scripts/run-frontend.sh   # 前端"
echo "   ./scripts/run-backend.sh    # 后端"
echo ""
echo "3. 访问应用:"
echo "   http://localhost:3000"
echo ""
