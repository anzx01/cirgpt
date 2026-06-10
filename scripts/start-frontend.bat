@echo off
chcp 65001 >nul
REM CircuitGPT 前端启动脚本 (Windows)

title CircuitGPT Frontend

echo ========================================
echo CircuitGPT 前端服务启动
echo ========================================
echo.

REM 切换到前端目录
cd /d "%~dp0\..\frontend"

REM 检查 node_modules
if not exist "node_modules" (
    echo [错误] node_modules 不存在
    echo.
    echo 请先运行安装:
    echo   cd frontend
    echo   npm install
    echo.
    pause
    exit /b 1
)

REM 检查 .env.local
if not exist ".env.local" (
    echo [警告] .env.local 不存在
    if exist ".env.local.example" (
        echo 正在从示例创建 .env.local...
        copy .env.local.example .env.local >nul
        echo [完成] 已创建 .env.local
    )
)

REM 创建PID文件目录
if not exist "..\scripts\.pids" mkdir "..\scripts\.pids"

echo.
echo [启动] 正在启动开发服务器...
echo.
echo 访问地址: http://localhost:3000
echo.
echo 提示: 按 Ctrl+C 停止服务
echo       或运行 stop-frontend.bat
echo.

REM 启动并记录进程ID
start "CircuitGPT Frontend" /B npm run dev

REM 等待几秒让服务启动
timeout /t 3 /nobreak >nul

REM 查找并保存进程ID
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq CircuitGPT Frontend*" /FO LIST ^| find "PID:"') do (
    echo %%a > ..\scripts\.pids\frontend.pid
    echo [信息] 进程ID: %%a
)

echo.
echo [完成] 前端服务已启动
echo.
echo 按任意键关闭此窗口（服务将继续运行）
pause >nul
