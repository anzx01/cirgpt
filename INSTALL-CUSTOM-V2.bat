@echo off
REM Install dependencies using Python 3.10

echo ========================================
echo   Installing Dependencies
echo ========================================
echo.

echo [1/3] Installing Backend dependencies...
call backend\venv\Scripts\activate.bat
cd backend
pip install -r requirements.txt
cd ..
deactivate

echo.
echo [2/3] Installing AI Service dependencies...
call ai_service\venv\Scripts\activate.bat
cd ai_service
pip install -r requirements.txt
cd ..
deactivate

echo.
echo [3/3] Installing EDA Tools dependencies...
call eda_tools\venv\Scripts\activate.bat
cd eda_tools
pip install -r requirements.txt
cd ..
deactivate

echo.
echo [4/4] Initializing database...
cd backend
D:\Python\Python310\python.exe init_db.py
cd ..

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo You can now run START-CUSTOM.bat to start all services
echo.
pause
