@echo off
chcp 65001 >nul
REM CircuitGPT 全部服务停止脚本 (Windows)

title CircuitGPT Stop All

echo ========================================
echo CircuitGPT 全部服务停止
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 停止前端服务...
call stop-frontend.bat >nul 2>&1
echo [完成] 前端服务已停止

echo.
echo [2/2] 停止后端服务...
call stop-backend.bat >nul 2>&1
echo [完成] 后端服务已停止

echo.
echo ========================================
echo 全部服务已停止
echo ========================================
echo.
echo 按任意键退出...
pause >nul
