@echo off
REM CircuitGPT Full Service Startup Script (Windows)

title CircuitGPT Start All

echo ========================================
echo CircuitGPT Full Service Startup
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Starting backend service...
echo.
start "" "%~dp0start-backend.bat"

REM Wait for backend to start
timeout /t 5 /nobreak >/dev/null

echo.
echo [2/3] Starting frontend service...
echo.
start "" "%~dp0start-frontend.bat"

REM Wait for frontend to start
timeout /t 5 /nobreak >/dev/null

echo.
echo [3/3] Checking service status...
echo.

REM Check backend
curl -s http://localhost:8000/ >/dev/null 2>&1
if %errorlevel% equ 0 (
    echo [OK] Backend running: http://localhost:8000
) else (
    echo [X] Backend not responding
)

REM Check frontend
curl -s http://localhost:3000/ >/dev/null 2>&1
if %errorlevel% equ 0 (
    echo [OK] Frontend running: http://localhost:3000
) else (
    echo [X] Frontend not responding (may still be starting)
)

echo.
echo ========================================
echo Startup Complete
echo ========================================
echo.
echo Access URLs:
echo   Frontend: http://localhost:3000
echo   Backend: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
echo To stop services:
echo   Run stop-all.bat
echo.
echo Press any key to exit...
pause >/dev/null
