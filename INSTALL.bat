@echo off
REM AI Circuit Designer - Installation Script
REM Double-click this file to install all dependencies

echo ========================================
echo   AI Circuit Designer - Installation
echo ========================================
echo.

REM Check Python
echo [1/4] Checking Python...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.10+ from: https://www.python.org/
    pause
    exit /b 1
)
echo OK
echo.

REM Check Node.js
echo [2/4] Checking Node.js...
node --version
if %errorlevel% neq 0 (
    echo ERROR: Node.js not found!
    echo Please install Node.js 18+ from: https://nodejs.org/
    pause
    exit /b 1
)
echo OK
echo.

REM Install Python dependencies
echo [3/4] Installing Python dependencies...
echo.

cd /d "%~dp0backend"
echo Installing Backend dependencies...
python -m pip install -r requirements.txt
echo.

cd /d "%~dp0ai_service"
echo Installing AI Service dependencies...
python -m pip install -r requirements.txt
echo.

cd /d "%~dp0eda_tools"
echo Installing EDA Tools dependencies...
python -m pip install -r requirements.txt
echo.

cd /d "%~dp0"

REM Install Node.js dependencies
echo [4/4] Installing Frontend dependencies...
cd frontend
call npm install
cd ..

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Start Redis: redis-server
echo   2. Initialize database: cd backend && python init_db.py
echo   3. Run START.bat to start all services
echo.
pause
