# Redis Installation Script for Windows
# Run this script to install Redis

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Redis Installation for Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Redis is already installed
Write-Host "Checking if Redis is installed..." -ForegroundColor Yellow
try {
    $redisProcess = Get-Process -Name redis-server -ErrorAction SilentlyContinue
    if ($redisProcess) {
        Write-Host "✓ Redis is already running!" -ForegroundColor Green
        Write-Host ""
        Write-Host "You can proceed with: .\START-FULL.bat" -ForegroundColor Cyan
        Read-Host "Press Enter to exit"
        exit 0
    }
} catch {}

$redisExists = Get-Command redis-server -ErrorAction SilentlyContinue
if ($redisExists) {
    Write-Host "✓ Redis is installed but not running" -ForegroundColor Green
    Write-Host ""
    Write-Host "To start Redis, run in a separate terminal:" -ForegroundColor Cyan
    Write-Host "  redis-server" -ForegroundColor White
    Read-Host "Press Enter to exit"
    exit 0
}

Write-Host "✗ Redis is NOT installed" -ForegroundColor Red
Write-Host ""
Write-Host "Please choose an installation method:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Install Redis using winget (Recommended, Easiest)" -ForegroundColor Green
Write-Host "2. Install Memurai (Redis-compatible for Windows)" -ForegroundColor Cyan
Write-Host "3. Download Redis manually from GitHub" -ForegroundColor Yellow
Write-Host "4. Skip (install manually later)" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "Enter your choice (1-4)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Installing Redis using winget..." -ForegroundColor Yellow
        Write-Host ""

        try {
            winget install Redis.Redis --accept-package-agreements --accept-source-agreements

            Write-Host ""
            Write-Host "✓ Redis installed successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host "To start Redis, run in a separate terminal:" -ForegroundColor Cyan
            Write-Host "  redis-server" -ForegroundColor White
            Write-Host ""
            Write-Host "Then run: .\START-FULL.bat" -ForegroundColor Cyan
        } catch {
            Write-Host ""
            Write-Host "✗ winget installation failed" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please try Method 2 or 3" -ForegroundColor Yellow
        }
    }
    "2" {
        Write-Host ""
        Write-Host "Opening Memurai download page..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Memurai is a Redis-compatible platform for Windows." -ForegroundColor Cyan
        Write-Host ""

        # Open Memurai download page
        Start-Process "https://www.memurai.com/get-memurai/"

        Write-Host "Please:" -ForegroundColor Yellow
        Write-Host "  1. Download Memurai Developer Edition (Free)" -ForegroundColor White
        Write-Host "  2. Install Memurai" -ForegroundColor White
        Write-Host "  3. Run: memurai-server (instead of redis-server)" -ForegroundColor White
        Write-Host ""
        Write-Host "Note: Update START-FULL.bat to use 'memurai-server' instead of 'redis-server'" -ForegroundColor Gray
    }
    "3" {
        Write-Host ""
        Write-Host "Opening Redis download page..." -ForegroundColor Yellow
        Write-Host ""

        # Open Redis for Windows download page
        Start-Process "https://github.com/microsoftarchive/redis/releases"

        Write-Host "Please:" -ForegroundColor Yellow
        Write-Host "  1. Download the latest .msi file (e.g., Redis-x64-3.x.x.msi)" -ForegroundColor White
        Write-Host "  2. Run the installer" -ForegroundColor White
        Write-Host "  3. After installation, run: redis-server" -ForegroundColor White
    }
    "4" {
        Write-Host ""
        Write-Host "Skipping Redis installation." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "WARNING: The application will NOT work without Redis!" -ForegroundColor Red
        Write-Host ""
        Write-Host "To install Redis later:" -ForegroundColor Cyan
        Write-Host "  1. Run: .\install-redis.ps1" -ForegroundColor White
        Write-Host "  2. Or: winget install Redis.Redis" -ForegroundColor White
    }
    default {
        Write-Host ""
        Write-Host "Invalid choice. Exiting." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
