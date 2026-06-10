#!/bin/bash
# CircuitGPT 快速启动指南

echo "========================================"
echo "CircuitGPT 快速启动指南"
echo "========================================"
echo ""

# 检查是否在项目根目录
if [ ! -f "package.json" ] && [ ! -d "frontend" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    echo "当前目录: $(pwd)"
    exit 1
fi

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "项目根目录: $PROJECT_ROOT"
echo ""

# 检查安装状态
echo "检查安装状态..."
echo ""

# 检查前端
if [ -d "frontend/node_modules" ]; then
    echo "✓ 前端依赖已安装"
    echo "  - Next.js 15.5.19"
    echo "  - React 19.2.7"
else
    echo "✗ 前端依赖未安装"
    echo "  运行: cd frontend && npm install"
fi

# 检查后端配置
if [ -f "backend/.env" ]; then
    echo "✓ 后端配置已完成"
    if grep -q "SECRET_KEY=NYHdEa4GHSo6Zfkq" backend/.env 2>/dev/null; then
        echo "  - SECRET_KEY: 已配置（32字符）"
    fi
else
    echo "✗ 后端配置未完成"
    echo "  查看: backend/CONFIG_SETUP.md"
fi

echo ""
echo "========================================"
echo "启动服务"
echo "========================================"
echo ""

# 询问用户要启动什么
echo "请选择要启动的服务:"
echo "  1) 前端 (http://localhost:3000)"
echo "  2) 后端 (http://localhost:8000)"
echo "  3) 两者都启动"
echo "  4) 查看详细安装报告"
echo "  q) 退出"
echo ""
read -p "请输入选项 [1-4/q]: " choice

case $choice in
    1)
        echo ""
        echo "启动前端..."
        cd frontend
        npm run dev
        ;;
    2)
        echo ""
        echo "启动后端..."
        cd backend
        if [ -d "venv" ]; then
            source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null
        fi
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
        ;;
    3)
        echo ""
        echo "同时启动需要打开两个终端："
        echo ""
        echo "终端1 - 前端:"
        echo "  cd frontend && npm run dev"
        echo ""
        echo "终端2 - 后端:"
        echo "  cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
        echo ""
        ;;
    4)
        echo ""
        if [ -f "INSTALLATION_COMPLETE.md" ]; then
            cat INSTALLATION_COMPLETE.md | less
        else
            echo "安装报告文件未找到"
        fi
        ;;
    q|Q)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac
