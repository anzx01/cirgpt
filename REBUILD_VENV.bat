@echo off
REM Rebuild virtual environments with Python 3.10

echo ========================================
echo   Rebuilding Virtual Environments
echo ========================================
echo.

REM Delete old virtual environments
echo [1/4] Removing old virtual environments...
if exist "backend\venv" rmdir /s /q "backend\venv"
if exist "ai_service\venv" rmdir /s /q "ai_service\venv"
if exist "eda_tools\venv" rmdir /s /q "eda_tools\venv"
echo   Removed old virtual environments.

REM Create new virtual environments with Python 3.10
set "PYTHON_EXE=py -3.10"
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    set "PYTHON_EXE=python"
)
echo.
echo [2/4] Creating Backend virtual environment...
%PYTHON_EXE% -m venv backend\venv
echo   Created Backend venv.

echo.
echo [3/4] Creating AI Service virtual environment...
%PYTHON_EXE% -m venv ai_service\venv
echo   Created AI Service venv.

echo.
echo [4/4] Creating EDA Tools virtual environment...
%PYTHON_EXE% -m venv eda_tools\venv
echo   Created EDA Tools venv.

echo.
echo ========================================
echo   Virtual Environments Rebuilt!
echo ========================================
echo.
echo Next step: Run INSTALL-CUSTOM.bat to install dependencies
echo.
pause
