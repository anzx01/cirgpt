@echo off
REM AI Circuit Designer - Startup Script with Full Python Path
REM This script uses C:\Python314\python.exe explicitly

echo ========================================
echo   AI Circuit Designer - Startup
echo ========================================
echo.
echo Using Python: C:\Python314\python.exe
echo.

set PYTHON_EXE=C:\Python314\python.exe

echo [1/6] Initializing database...
cd backend
"%PYTHON_EXE%" init_db.py
cd ..
timeout /t 2 /nobreak >nul

echo.
echo [2/6] Starting Backend API (port 8000)...
start "Backend API" cmd /k "cd backend && C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul

echo.
echo [3/6] Starting AI Service (port 8001)...
start "AI Service" cmd /k "cd ai_service && C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8001"
timeout /t 3 /nobreak >nul

echo.
echo [4/6] Starting EDA Service (port 8002)...
start "EDA Service" cmd /k "cd eda_tools && C:\Python314\python.exe -m uvicorn app.main:app --reload --port 8002"
timeout /t 3 /nobreak >nul

echo.
echo [5/6] Starting Celery Worker...
start "Celery Worker" cmd /k "cd backend && C:\Python314\python.exe start_worker.py"
timeout /t 2 /nobreak >nul

echo.
echo [6/6] Starting Frontend (port 3000)...
start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo   All Services Started!
echo ========================================
echo.
echo Access the application:
echo   Frontend:        http://localhost:3000
echo   Backend API:     http://localhost:8000/docs
echo   AI Service:      http://localhost:8001/docs
echo   EDA Service:     http://localhost:8002/docs
echo.
echo Note: Make sure Redis is running (redis-server)
echo.
pause
