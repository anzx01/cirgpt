@echo off
chcp 65001 >nul
REM CircuitGPT 前端停止脚本 (Windows)

title CircuitGPT Frontend Stop

echo ========================================
echo CircuitGPT 前端服务停止
echo ========================================
echo.

cd /d "%~dp0"

REM 检查PID文件
if exist ".pids\frontend.pid" (
    set /p PID=<.pids\frontend.pid
    echo [信息] 找到进程ID: %PID%
    echo.

    REM 检查进程是否存在
    tasklist /FI "PID eq %PID%" 2>NUL | find /I /N "node.exe">NUL
    if "%ERRORLEVEL%"=="0" (
        echo [停止] 正在停止前端服务...
        taskkill /PID %PID% /F /T >nul 2>&1
        echo [完成] 前端服务已停止
    ) else (
        echo [警告] 进程 %PID% 不存在或已停止
    )

    REM 删除PID文件
    del .pids\frontend.pid >nul 2>&1
) else (
    echo [警告] 未找到PID文件
    echo.
    echo 尝试查找所有Node.js进程...
    echo.

    REM 列出所有node进程
    tasklist /FI "IMAGENAME eq node.exe" /FO TABLE
    echo.

    set /p CONFIRM="是否停止所有Node.js进程？这可能影响其他Node应用 (Y/N): "
    if /i "%CONFIRM%"=="Y" (
        echo.
        echo [停止] 正在停止所有Node.js进程...
        taskkill /F /IM node.exe /T >nul 2>&1
        echo [完成] 已停止所有Node.js进程
    ) else (
        echo [取消] 未执行任何操作
    )
)

echo.
echo 按任意键退出...
pause >nul
