@echo off
REM AI Circuit Designer - Installation Script with Full Python Path
REM This script uses C:\Python314\python.exe explicitly

echo ========================================
echo   AI Circuit Designer - Installation
echo ========================================
echo.
echo Using Python: C:\Python314\python.exe
echo.

set PYTHON_EXE=C:\Python314\python.exe

REM Verify Python exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python not found at %PYTHON_EXE%
    echo Please check the path and update PYTHON_EXE in this script
    pause
    exit /b 1
)

echo [1/4] Checking Python...
"%PYTHON_EXE%" --version
if %errorlevel% neq 0 (
    echo ERROR: Python cannot be executed
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
"%PYTHON_EXE%" -m pip install -r requirements.txt
echo.

cd /d "%~dp0ai_service"
echo Installing AI Service dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt
echo.

cd /d "%~dp0eda_tools"
echo Installing EDA Tools dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt
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
echo   2. Initialize database:
echo      cd backend
echo      C:\Python314\python.exe init_db.py
echo      cd ..
echo   3. Run START-CUSTOM.bat to start all services
echo.
pause
