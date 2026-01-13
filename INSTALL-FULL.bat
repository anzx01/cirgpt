@echo off
REM AI Circuit Designer - Installation Script with Full Paths
REM Python: C:\Python314\python.exe
REM Node.js: C:\Program Files\nodejs\node.exe

echo ========================================
echo   AI Circuit Designer - Installation
echo ========================================
echo.
echo Python: C:\Python314\python.exe
echo Node.js: C:\Program Files\nodejs\node.exe
echo.

set PYTHON_EXE=C:\Python314\python.exe
set NODE_EXE=C:\Program Files\nodejs\node.exe
set NPM_EXE=C:\Program Files\nodejs\npm.cmd

REM Verify Python exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python not found at %PYTHON_EXE%
    pause
    exit /b 1
)

REM Verify Node.js exists
if not exist "%NODE_EXE%" (
    echo ERROR: Node.js not found at %NODE_EXE%
    pause
    exit /b 1
)

echo [1/5] Verifying installations...
echo.
echo Python version:
"%PYTHON_EXE%" --version
echo.
echo Node.js version:
"%NODE_EXE%" --version
echo.
echo npm version:
"%NPM_EXE%" --version
echo.

REM Install Python dependencies
echo [2/5] Installing Python dependencies...
echo.

cd /d "%~dp0backend"
echo Installing Backend dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pip
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
echo [3/5] Installing Frontend dependencies...
cd frontend
if not exist "node_modules" (
    echo Installing npm packages (this may take a few minutes)...
    call "%NPM_EXE%" install
) else (
    echo node_modules already exists, skipping...
)
cd ..
echo.

echo [4/5] Creating logs directory...
if not exist "logs" mkdir logs
if not exist "pids" mkdir pids
echo Created.
echo.

echo [5/5] Verifying installations...
echo.
echo Backend:
cd backend
"%PYTHON_EXE%" -c "import fastapi; print('✓ FastAPI:', fastapi.__version__)"
"%PYTHON_EXE%" -c "import uvicorn; print('✓ Uvicorn installed')"
cd ..
echo.

echo AI Service:
cd ai_service
"%PYTHON_EXE%" -c "import transformers; print('✓ Transformers installed')"
cd ..
echo.

echo EDA Tools:
cd eda_tools
"%PYTHON_EXE%" -c "import skidl; print('✓ SKiDL installed')" 2>nul || echo   ⚠ SKiDL not installed (optional)
cd ..
echo.

echo Frontend:
cd frontend
if exist "node_modules\@mui" (
    echo ✓ Material-UI installed
)
if exist "node_modules\socket.io-client" (
    echo ✓ Socket.io-client installed
)
if exist "node_modules\recharts" (
    echo ✓ Recharts installed
)
cd ..
echo.

echo ========================================
echo   ✅ Installation Complete!
echo ========================================
echo.
echo All dependencies have been installed successfully!
echo.
echo Next steps:
echo   1. Start Redis server (in a new terminal):
echo      redis-server
echo.
echo   2. Initialize database:
echo      cd backend
echo      C:\Python314\python.exe init_db.py
echo      cd ..
echo.
echo   3. Start all services:
echo      .\START-FULL.bat
echo.
echo Or start services manually in separate terminals:
echo   Terminal 1: redis-server
echo   Terminal 2: cd backend && C:\Python314\python.exe -m uvicorn app.main:app --port 8000
echo   Terminal 3: cd ai_service && C:\Python314\python.exe -m uvicorn app.main:app --port 8001
echo   Terminal 4: cd eda_tools && C:\Python314\python.exe -m uvicorn app.main:app --port 8002
echo   Terminal 5: cd backend && C:\Python314\python.exe start_worker.py
echo   Terminal 6: cd frontend && C:\Program Files\nodejs\npm.cmd run dev
echo.
echo.
pause
