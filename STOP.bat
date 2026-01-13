@echo off
REM Stop All AI Circuit Designer Services

echo ========================================
echo   Stopping All Services
echo ========================================
echo.

echo Closing service windows...
echo.

REM Kill all relevant processes
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul
taskkill /F /IM uvicorn.exe /T 2>nul
taskkill /F /IM celery.exe /T 2>nul

timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   ✅ All Services Stopped
echo ========================================
echo.
echo Note: Redis continues running.
echo Stop Redis manually with: redis-cli shutdown
echo.
pause
