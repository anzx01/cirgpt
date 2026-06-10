@echo off
chcp 65001 >nul
REM CircuitGPT 全部服务启动脚本 (Windows)

title CircuitGPT Start All

echo ========================================
echo CircuitGPT 全部服务启动
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 启动后端服务...
echo.
start "" "%~dp0start-backend.bat"

REM 等待后端启动
timeout /t 5 /nobreak >nul

echo.
echo [2/3] 启动前端服务...
echo.
start "" "%~dp0start-frontend.bat"

REM 等待前端启动
timeout /t 5 /nobreak >nul

echo.
echo [3/3] 检查服务状态...
echo.

REM 检查后端
curl -s http://localhost:8000/ >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] 后端服务运行中: http://localhost:8000
) else (
    echo [✗] 后端服务未响应
)

REM 检查前端
curl -s http://localhost:3000/ >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] 前端服务运行中: http://localhost:3000
) else (
    echo [✗] 前端服务未响应（可能还在启动中）
)

echo.
echo ========================================
echo 启动完成
echo ========================================
echo.
echo 访问地址:
echo   前端: http://localhost:3000
echo   后端: http://localhost:8000
echo   API文档: http://localhost:8000/docs
echo.
echo 停止服务:
echo   运行 stop-all.bat
echo.
echo 按任意键退出...
pause >nul
