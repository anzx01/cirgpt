@echo off
REM Install dependencies using Python 3.11

echo ========================================
echo   Installing Dependencies
echo   Using Python 3.11
echo ========================================
echo.

echo This will take 5-10 minutes, especially for AI Service (PyTorch)
echo Please be patient...
echo.

echo [1/4] Installing Backend dependencies...
call backend\venv\Scripts\activate.bat
cd backend
echo Installing FastAPI, SQLAlchemy, Celery, etc...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Backend installation failed
    cd ..
    deactivate
    pause
    exit /b 1
)
cd ..
deactivate
echo   Backend dependencies installed successfully.
echo.

echo [2/4] Installing AI Service dependencies...
echo This will download PyTorch (~2GB) and Transformers - may take several minutes
call ai_service\venv\Scripts\activate.bat
cd ai_service
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: AI Service installation failed
    cd ..
    deactivate
    pause
    exit /b 1
)
cd ..
deactivate
echo   AI Service dependencies installed successfully.
echo.

echo [3/4] Installing EDA Tools dependencies...
call eda_tools\venv\Scripts\activate.bat
cd eda_tools
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: EDA Tools installation failed
    cd ..
    deactivate
    pause
    exit /b 1
)
cd ..
deactivate
echo   EDA Tools dependencies installed successfully.
echo.

echo [4/4] Initializing database...
cd backend
python init_db.py
if %errorlevel% neq 0 (
    echo ERROR: Database initialization failed
    cd ..
    pause
    exit /b 1
)
cd ..
echo   Database initialized successfully.
echo.

echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo All dependencies have been installed successfully!
echo.
echo You can now run START.bat to start all services
echo.
echo Services will be available at:
echo   - Frontend:        http://localhost:3000
echo   - Backend API:     http://localhost:8000/docs
echo   - AI Service:      http://localhost:8001/docs
echo   - EDA Service:     http://localhost:8002/docs
echo.
pause
