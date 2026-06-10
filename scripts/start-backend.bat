@echo off
chcp 65001 >nul
REM CircuitGPT 后端启动脚本 (Windows)

title CircuitGPT Backend

echo ========================================
echo CircuitGPT 后端服务启动
echo ========================================
echo.

REM 切换到后端目录
cd /d "%~dp0\..\backend"

REM 检查 .env 文件
if not exist ".env" (
    echo [错误] .env 文件不存在
    echo.
    echo 请先配置后端:
    echo   1. cd backend
    echo   2. python -c "import secrets; print(secrets.token_urlsafe(32))"
    echo   3. copy .env.example .env
    echo   4. 编辑 .env，填入生成的 SECRET_KEY
    echo.
    echo 详细说明: backend\CONFIG_SETUP.md
    echo.
    pause
    exit /b 1
)

REM 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo [信息] 发现虚拟环境，正在激活...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [信息] 发现虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
) else (
    echo [警告] 未找到虚拟环境
    echo [信息] 将使用系统Python
)

REM 检查uvicorn
python -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo [错误] uvicorn 未安装
    echo.
    echo 请先安装依赖:
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM 创建PID文件目录
if not exist "..\scripts\.pids" mkdir "..\scripts\.pids"

REM 创建日志目录
if not exist "logs" mkdir logs

echo.
echo [启动] 正在启动后端服务...
echo.
echo API地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
echo 提示: 按 Ctrl+C 停止服务
echo       或运行 stop-backend.bat
echo.

REM 启动服务
start "CircuitGPT Backend" /B python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

REM 等待几秒让服务启动
timeout /t 3 /nobreak >nul

REM 查找并保存进程ID
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq CircuitGPT Backend*" /FO LIST ^| find "PID:"') do (
    echo %%a > ..\scripts\.pids\backend.pid
    echo [信息] 进程ID: %%a
)

echo.
echo [完成] 后端服务已启动
echo.
echo 按任意键关闭此窗口（服务将继续运行）
pause >nul
