@echo off
REM Redis Installation Script for Windows

echo ========================================
echo   Redis Installation for Windows
echo ========================================
echo.

echo Redis is not installed on your system.
echo.
echo Please choose an installation method:
echo.
echo [1] Download Redis for Windows (Recommended)
echo     - Download from GitHub
echo     - Extract and run
echo.
echo [2] Use Memurai (Redis-compatible)
echo     - Redis clone for Windows
echo     - Free and easy to install
echo.
echo [3] Skip Redis installation
echo     - You can install it manually later
echo.
echo Note: Redis is REQUIRED for this application to work
echo.

set /p choice="Enter your choice (1, 2, or 3): "

if "%choice%"=="1" goto :download_redis
if "%choice%"=="2" goto :download_memurai
if "%choice%"=="3" goto :skip
goto :end

:download_redis
echo.
echo Opening Redis download page...
echo.
echo Please:
echo 1. Download Redis-x64-3.x.x.msi
echo 2. Install Redis
echo 3. Run: redis-server
echo.
start https://github.com/microsoftarchive/redis/releases
goto :end

:download_memurai
echo.
echo Opening Memurai download page...
echo.
echo Please:
echo 1. Download Memurai Developer Edition
echo 2. Install Memurai
echo 3. Run: memurai-server (instead of redis-server)
echo.
start https://www.memurai.com/get-memurai/
goto :end

:skip
echo.
echo Skipping Redis installation.
echo.
echo WARNING: The application will NOT work without Redis!
echo Please install Redis manually before running START-FULL.bat
echo.
goto :end

:end
echo.
echo After installing Redis, run it in a separate terminal:
echo   redis-server
echo.
pause
