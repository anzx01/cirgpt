@echo off
chcp 65001 >nul
REM CircuitGPT 后端停止脚本 (Windows)

title CircuitGPT Backend Stop

echo ========================================
echo CircuitGPT 后端服务停止
echo ========================================
echo.

cd /d "%~dp0"

REM 检查PID文件
if exist ".pids\backend.pid" (
    set /p PID=<.pids\backend.pid
    echo [信息] 找到进程ID: %PID%
    echo.

    REM 检查进程是否存在
    tasklist /FI "PID eq %PID%" 2>NUL | find /I /N "python.exe">NUL
    if "%ERRORLEVEL%"=="0" (
        echo [停止] 正在停止后端服务...
        taskkill /PID %PID% /F /T >nul 2>&1
        echo [完成] 后端服务已停止
    ) else (
        echo [警告] 进程 %PID% 不存在或已停止
    )

    REM 删除PID文件
    del .pids\backend.pid >nul 2>&1
) else (
    echo [警告] 未找到PID文件
    echo.
    echo 尝试查找uvicorn进程...
    echo.

    REM 查找uvicorn进程
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| find "PID:"') do (
        wmic process where "ProcessId=%%a" get CommandLine 2>nul | find "uvicorn" >nul
        if not errorlevel 1 (
            echo [找到] Uvicorn进程: %%a
            taskkill /PID %%a /F /T >nul 2>&1
            echo [停止] 已停止进程 %%a
        )
    )

    echo.
    echo [完成] 已尝试停止所有uvicorn进程
)

echo.
echo 按任意键退出...
pause >nul
