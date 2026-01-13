@echo off
REM AI Circuit Designer - Startup Script with Full Paths
REM Python: C:\Python314\python.exe
REM Node.js: C:\Program Files\nodejs

echo ========================================
echo   AI Circuit Designer - Starting All Services
echo ========================================
echo.
echo Python: C:\Python314\python.exe
echo Node.js: C:\Program Files\nodejs
echo.

set PYTHON_EXE=C:\Python314\python.exe
set NODEEXE=C:\Program Files\nodejs
set NPM_CMD=%NODEEXE%\npm.cmd

REM Check if Redis is running
echo [1/7] Checking Redis...
tasklist /FI "IMAGENAME eq redis-server.exe" 2>NUL | find /I /N "redis-server.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo ✓ Redis is running
) else (
    echo ⚠ Redis is NOT running!
    echo.
    echo Please start Redis in a separate terminal:
    echo   redis-server
    echo.
    echo Press Enter to continue anyway (services will fail without Redis)...
    pause
)
echo.

REM Initialize database
echo [2/7] Initializing database...
cd backend
if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" init_db.py
    if %errorlevel% equ 0 (
        echo ✓ Database initialized
    ) else (
        echo ⚠ Database initialization had issues (this is OK if already initialized)
    )
) else (
    echo ⚠ Could not find Python at %PYTHON_EXE%
)
cd ..
timeout /t 2 /nobreak >nul
echo.

REM Start Backend API
echo [3/7] Starting Backend API (port 8000)...
start "Backend API" cmd /k "title Backend API ^| cd /d %~dp0backend ^| C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
echo ✓ Backend API starting...
echo.

REM Start AI Service
echo [4/7] Starting AI Service (port 8001)...
start "AI Service" cmd /k "title AI Service ^| cd /d %~dp0ai_service ^| C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8001"
timeout /t 3 /nobreak >nul
echo ✓ AI Service starting...
echo.

REM Start EDA Service
echo [5/7] Starting EDA Service (port 8002)...
start "EDA Service" cmd /k "title EDA Service ^| cd /d %~dp0eda_tools ^| C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8002"
timeout /t 3 /nobreak >nul
echo ✓ EDA Service starting...
echo.

REM Start Celery Worker
echo [6/7] Starting Celery Worker...
start "Celery Worker" cmd /k "title Celery Worker ^| cd /d %~dp0backend ^| C:\Python314\python.exe start_worker.py"
timeout /t 2 /nobreak >nul
echo ✓ Celery Worker starting...
echo.

REM Start Frontend
echo [7/7] Starting Frontend (port 3000)...
cd frontend
if not exist "node_modules" (
    echo Installing frontend dependencies first...
    call "%NPM_CMD%" install
)
start "Frontend" cmd /k "title Frontend ^| cd /d %~dp0frontend ^| C:\Program Files\nodejs\npm.cmd run dev"
cd ..
echo ✓ Frontend starting...
echo.

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   ✅ All Services Started!
echo ========================================
echo.
echo 🌐 Access the application:
echo.
echo    Frontend:        http://localhost:3000
echo    Backend API:     http://localhost:8000/docs
echo    AI Service:      http://localhost:8001/docs
echo    EDA Service:     http://localhost:8002/docs
echo.
echo 📝 Service windows:
echo    - Backend API (port 8000)
echo    - AI Service (port 8001)
echo    - EDA Service (port 8002)
echo    - Celery Worker
echo    - Frontend (port 3000)
echo.
echo 💡 Tips:
echo    - Keep all windows open for the app to work
echo    - Close windows to stop individual services
echo    - Check each window for logs and errors
echo.
echo 🛑 To stop all services:
echo    Close all the opened command windows
echo    Or press Ctrl+C in each window
echo.
echo ⚠ Note: Redis should continue running in its own window
echo.
pause
