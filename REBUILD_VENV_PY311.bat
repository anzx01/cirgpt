@echo off
REM Rebuild virtual environments with Python 3.11

echo ========================================
echo   Rebuilding Virtual Environments
echo   Using Python 3.11
echo ========================================
echo.

REM Check if Python 3.11 is available
py -3.11 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3.11 not found!
    echo Please install Python 3.11 first:
    echo   winget install Python.Python.3.11
    echo.
    pause
    exit /b 1
)

echo Python 3.11 detected:
py -3.11 --version
echo.

REM Delete old virtual environments
echo [1/4] Removing old virtual environments...
if exist "backend\venv" (
    rmdir /s /q "backend\venv"
    echo   Removed backend\venv
)
if exist "ai_service\venv" (
    rmdir /s /q "ai_service\venv"
    echo   Removed ai_service\venv
)
if exist "eda_tools\venv" (
    rmdir /s /q "eda_tools\venv"
    echo   Removed eda_tools\venv
)
echo.

REM Create new virtual environments with Python 3.11
echo [2/4] Creating Backend virtual environment...
py -3.11 -m venv backend\venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create backend venv
    pause
    exit /b 1
)
echo   Created Backend venv.

echo [3/4] Creating AI Service virtual environment...
py -3.11 -m venv ai_service\venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create AI service venv
    pause
    exit /b 1
)
echo   Created AI Service venv.

echo [4/4] Creating EDA Tools virtual environment...
py -3.11 -m venv eda_tools\venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create EDA tools venv
    pause
    exit /b 1
)
echo   Created EDA Tools venv.

echo.
echo ========================================
echo   Virtual Environments Rebuilt!
echo ========================================
echo.
echo Next steps:
echo   1. Run INSTALL-PY311.bat to install dependencies
echo   2. Run START.bat to start all services
echo.
pause
