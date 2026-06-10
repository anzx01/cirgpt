@echo off
chcp 65001 >nul
REM CircuitGPT 服务状态检查脚本 (Windows)

title CircuitGPT Status

echo ========================================
echo CircuitGPT 服务状态检查
echo ========================================
echo.

cd /d "%~dp0"

REM 检查前端进程
echo [前端服务]
if exist ".pids\frontend.pid" (
    set /p FRONTEND_PID=<.pids\frontend.pid
    tasklist /FI "PID eq %FRONTEND_PID%" 2>NUL | find /I /N "node.exe">NUL
    if "%ERRORLEVEL%"=="0" (
        echo   状态: [运行中]
        echo   进程ID: %FRONTEND_PID%
        echo   地址: http://localhost:3000
    ) else (
        echo   状态: [已停止]
    )
) else (
    echo   状态: [未启动]
)

echo.

REM 检查后端进程
echo [后端服务]
if exist ".pids\backend.pid" (
    set /p BACKEND_PID=<.pids\backend.pid
    tasklist /FI "PID eq %BACKEND_PID%" 2>NUL | find /I /N "python.exe">NUL
    if "%ERRORLEVEL%"=="0" (
        echo   状态: [运行中]
        echo   进程ID: %BACKEND_PID%
        echo   地址: http://localhost:8000
        echo   API文档: http://localhost:8000/docs
    ) else (
        echo   状态: [已停止]
    )
) else (
    echo   状态: [未启动]
)

echo.
echo ========================================
echo 网络端口检查
echo ========================================
echo.

REM 检查端口占用
netstat -ano | findstr ":3000" >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] 端口 3000 (前端) 正在使用
) else (
    echo [✗] 端口 3000 (前端) 空闲
)

netstat -ano | findstr ":8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] 端口 8000 (后端) 正在使用
) else (
    echo [✗] 端口 8000 (后端) 空闲
)

echo.
echo ========================================
echo 按任意键退出...
pause >nul
