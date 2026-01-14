@echo off
REM 清理无用的缓存和临时文件

echo ========================================
echo 清理项目无用文件
echo ========================================
echo.

REM 清理 Python 缓存
echo [1/4] 清理 Python 缓存文件...
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    echo 删除: %%d
    rmdir /s /q "%%d" 2>nul
)
for /r . %%f in (*.pyc) do @if exist "%%f" (
    del /f /q "%%f" 2>nul
)
echo Python 缓存清理完成
echo.

REM 清理 Next.js 构建缓存
echo [2/4] 清理 Next.js 构建缓存...
if exist "frontend\.next" (
    echo 删除: frontend\.next
    rmdir /s /q "frontend\.next" 2>nul
)
echo Next.js 缓存清理完成
echo.

REM 清理日志文件
echo [3/4] 清理日志文件...
for /r . %%f in (*.log) do @if exist "%%f" (
    del /f /q "%%f" 2>nul
)
echo 日志文件清理完成
echo.

REM 清理其他临时文件
echo [4/4] 清理其他临时文件...
for /r . %%f in (.DS_Store *.tmp *.swp *.swo) do @if exist "%%f" (
    del /f /q "%%f" 2>nul
)
echo 临时文件清理完成
echo.

echo ========================================
echo 清理完成！
echo ========================================
pause
