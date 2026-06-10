@echo off
chcp 65001 >nul
REM 创建桌面快捷方式

echo ========================================
echo 创建 CircuitGPT 桌面快捷方式
echo ========================================
echo.

REM 获取桌面路径
for /f "usebackq tokens=3*" %%A in (`reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop`) do set DESKTOP=%%B
for /f "tokens=*" %%a in ('echo %DESKTOP%') do set DESKTOP=%%a

echo 桌面路径: %DESKTOP%
echo.

REM 创建VBS脚本
set VBS_FILE=%TEMP%\create_shortcut.vbs
echo Set oWS = WScript.CreateObject("WScript.Shell") > %VBS_FILE%
echo sLinkFile = "%DESKTOP%\CircuitGPT.lnk" >> %VBS_FILE%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %VBS_FILE%
echo oLink.TargetPath = "%~dp0menu.bat" >> %VBS_FILE%
echo oLink.WorkingDirectory = "%~dp0" >> %VBS_FILE%
echo oLink.Description = "CircuitGPT 控制面板" >> %VBS_FILE%
echo oLink.IconLocation = "%%SystemRoot%%\System32\shell32.dll,77" >> %VBS_FILE%
echo oLink.Save >> %VBS_FILE%

REM 执行VBS
cscript //nologo %VBS_FILE%

REM 删除临时VBS
del %VBS_FILE%

echo.
echo [✓] 快捷方式已创建到桌面
echo.
echo 文件名: CircuitGPT.lnk
echo.
pause
