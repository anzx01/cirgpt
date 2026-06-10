@echo off
REM CircuitGPT 前端快速启动脚本 (Windows)

echo ========================================
echo CircuitGPT 前端服务启动
echo ========================================
echo.

cd /d "%~dp0\..\frontend"

if not exist "node_modules" (
    echo 错误: node_modules 不存在
    echo 请先运行: npm install
    pause
    exit /b 1
)

if not exist ".env.local" (
    echo 警告: .env.local 不存在
    if exist ".env.local.example" (
        echo 正在创建 .env.local...
        copy .env.local.example .env.local
    )
)

echo.
echo 启动开发服务器...
echo 访问地址: http://localhost:3000
echo.
echo 按 Ctrl+C 停止服务
echo.

npm run dev
