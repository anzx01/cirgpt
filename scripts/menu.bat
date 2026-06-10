@echo off
chcp 65001 >nul
REM CircuitGPT 主菜单脚本 (Windows)

title CircuitGPT 控制面板

:MENU
cls
echo ========================================
echo       CircuitGPT 控制面板
echo ========================================
echo.
echo  [1] 启动全部服务
echo  [2] 启动前端服务
echo  [3] 启动后端服务
echo.
echo  [4] 停止全部服务
echo  [5] 停止前端服务
echo  [6] 停止后端服务
echo.
echo  [7] 查看服务状态
echo  [8] 查看安装报告
echo  [9] 打开浏览器
echo.
echo  [0] 退出
echo.
echo ========================================
echo.

set /p CHOICE="请选择操作 [0-9]: "

if "%CHOICE%"=="1" goto START_ALL
if "%CHOICE%"=="2" goto START_FRONTEND
if "%CHOICE%"=="3" goto START_BACKEND
if "%CHOICE%"=="4" goto STOP_ALL
if "%CHOICE%"=="5" goto STOP_FRONTEND
if "%CHOICE%"=="6" goto STOP_BACKEND
if "%CHOICE%"=="7" goto STATUS
if "%CHOICE%"=="8" goto REPORT
if "%CHOICE%"=="9" goto BROWSER
if "%CHOICE%"=="0" goto EXIT

echo.
echo [错误] 无效选项
timeout /t 2 /nobreak >nul
goto MENU

:START_ALL
cls
call "%~dp0start-all.bat"
goto MENU

:START_FRONTEND
cls
call "%~dp0start-frontend.bat"
goto MENU

:START_BACKEND
cls
call "%~dp0start-backend.bat"
goto MENU

:STOP_ALL
cls
call "%~dp0stop-all.bat"
goto MENU

:STOP_FRONTEND
cls
call "%~dp0stop-frontend.bat"
goto MENU

:STOP_BACKEND
cls
call "%~dp0stop-backend.bat"
goto MENU

:STATUS
cls
call "%~dp0status.bat"
goto MENU

:REPORT
cls
if exist "%~dp0..\INSTALLATION_COMPLETE.md" (
    type "%~dp0..\INSTALLATION_COMPLETE.md"
    echo.
    echo.
    echo ========================================
    pause
) else (
    echo [错误] 安装报告文件未找到
    timeout /t 2 /nobreak >nul
)
goto MENU

:BROWSER
echo.
echo 正在打开浏览器...
start http://localhost:3000
timeout /t 2 /nobreak >nul
goto MENU

:EXIT
cls
echo.
echo 感谢使用 CircuitGPT！
echo.
timeout /t 1 /nobreak >nul
exit
