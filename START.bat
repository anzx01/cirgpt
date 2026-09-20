@echo off
REM AI Circuit Designer - Quick Start (Windows Batch File)
REM Double-click this file to start all services

REM EDA toolchain paths (KiCad + ngspice). Set here so services find the
REM tools no matter how fresh the launching shell's environment is.
REM KiCad's install location differs between machines (which drive letter),
REM so auto-detect it: honor an already-set KICAD_ROOT, else probe the usual
REM spots on every drive, newest version first. The eda_tools service has
REM its own fallback scan, so leaving KICAD_ROOT empty here is still fine.
set "KICAD_DETECT="
if defined KICAD_ROOT if exist "%KICAD_ROOT%\bin\kicad-cli.exe" set "KICAD_DETECT=1"
if not defined KICAD_DETECT for %%L in (C D E F G H I J K) do (
    if not defined KICAD_DETECT for %%V in (10.0 9.0 8.0 7.0 6.0) do (
        if exist "%%L:\Program Files\KiCad\%%V\bin\kicad-cli.exe" (
            set "KICAD_ROOT=%%L:\Program Files\KiCad\%%V"
            set "KICAD_DETECT=1"
        )
    )
)
if defined KICAD_DETECT (
    echo [0/7] Using KiCad at %KICAD_ROOT%
) else (
    echo [0/7] WARNING: KiCad not found on any drive; set KICAD_ROOT manually.
)
if defined KICAD_ROOT set "PATH=%PATH%;%KICAD_ROOT%\bin"
set "PATH=%PATH%;%~dp0Spice64\bin"

echo ========================================
echo   AI Circuit Designer - Quick Start
echo ========================================
echo.

REM Check if project virtual environments are available.
REM The services run from their own venvs, so we do not require py -3.11
REM to be registered globally.
set "BACKEND_PY=backend\venv\Scripts\python.exe"
set "AI_PY=ai_service\venv\Scripts\python.exe"
set "EDA_PY=eda_tools\venv\Scripts\python.exe"

echo [1/7] Checking virtual environments...
echo.

REM Check if virtual environments exist
if not exist "backend\venv\Scripts\activate.bat" (
    echo ERROR: Backend virtual environment not found!
    echo Please run INSTALL-PY311.bat first
    pause
    exit /b 1
)
if not exist "ai_service\venv\Scripts\activate.bat" (
    echo ERROR: AI Service virtual environment not found!
    echo Please run INSTALL-PY311.bat first
    pause
    exit /b 1
)
if not exist "eda_tools\venv\Scripts\activate.bat" (
    echo ERROR: EDA Tools virtual environment not found!
    echo Please run INSTALL-PY311.bat first
    pause
    exit /b 1
)

echo.
echo [2/7] Starting Backend API (port 8000)...
start "Backend API" cmd /k "cd backend && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul

echo.
echo [3/7] Starting AI Service (port 8001)...
start "AI Service" cmd /k "cd ai_service && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --port 8001"
timeout /t 3 /nobreak >nul

echo.
echo [4/7] Starting EDA Service (port 8002)...
start "EDA Service" cmd /k "cd eda_tools && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --port 8002"
timeout /t 3 /nobreak >nul

echo.
echo [5/7] Starting Celery Worker...
start "Celery Worker" cmd /k "cd backend && call venv\Scripts\activate.bat && python start_worker.py"
timeout /t 2 /nobreak >nul

echo.
echo [6/7] Starting Frontend (port 3100)...
start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo   All Services Started!
echo ========================================
echo.
echo Access the application:
echo   Frontend:        http://localhost:3100
echo   Backend API:     http://localhost:8000/docs
echo   AI Service:      http://localhost:8001/docs
echo   EDA Service:     http://localhost:8002/docs
echo.
echo Note: Celery Worker is running for background tasks
echo       Redis is optional for this demo
echo.
pause
