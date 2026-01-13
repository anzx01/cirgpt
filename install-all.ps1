# AI Circuit Designer - Complete Installation Script
# PowerShell script to install all dependencies

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI Circuit Designer - Installation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "📋 [1/6] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.10+ from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Or activate your virtual environment" -ForegroundColor Yellow
    exit 1
}

# Check Node.js
Write-Host ""
Write-Host "📋 [2/6] Checking Node.js installation..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "✅ Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Node.js 18+ from: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Check Redis
Write-Host ""
Write-Host "📋 [3/6] Checking Redis installation..." -ForegroundColor Yellow
try {
    $redisVersion = redis-cli --version 2>&1
    Write-Host "✅ Redis found: $redisVersion" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Redis not found in PATH" -ForegroundColor Yellow
    Write-Host "   Please install Redis from: https://redis.io/download" -ForegroundColor Gray
    Write-Host "   Or use: winget install Redis.Redis" -ForegroundColor Gray
}

# Install Backend dependencies
Write-Host ""
Write-Host "📦 [4/6] Installing Backend dependencies..." -ForegroundColor Yellow
Set-Location backend
if (Test-Path "requirements.txt") {
    Write-Host "   Installing: requirements.txt" -ForegroundColor Gray
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Backend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Backend installation had issues" -ForegroundColor Red
    }
} else {
    Write-Host "❌ requirements.txt not found in backend/" -ForegroundColor Red
}
Set-Location ..

# Install AI Service dependencies
Write-Host ""
Write-Host "📦 [5/6] Installing AI Service dependencies..." -ForegroundColor Yellow
Set-Location ai_service
if (Test-Path "requirements.txt") {
    Write-Host "   Installing: requirements.txt" -ForegroundColor Gray
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ AI Service dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "⚠️  AI Service installation had issues" -ForegroundColor Red
    }
} else {
    Write-Host "❌ requirements.txt not found in ai_service/" -ForegroundColor Red
}
Set-Location ..

# Install EDA Tools dependencies
Write-Host ""
Write-Host "📦 [6/6] Installing EDA Tools dependencies..." -ForegroundColor Yellow
Set-Location eda_tools
if (Test-Path "requirements.txt") {
    Write-Host "   Installing: requirements.txt" -ForegroundColor Gray
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ EDA Tools dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "⚠️  EDA Tools installation had issues" -ForegroundColor Red
    }
} else {
    Write-Host "❌ requirements.txt not found in eda_tools/" -ForegroundColor Red
}
Set-Location ..

# Install Frontend dependencies
Write-Host ""
Write-Host "📦 [7/7] Installing Frontend dependencies..." -ForegroundColor Yellow
Set-Location frontend
if (Test-Path "package.json") {
    Write-Host "   Installing: npm dependencies" -ForegroundColor Gray
    npm install
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Frontend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Frontend installation had issues" -ForegroundColor Red
    }
} else {
    Write-Host "❌ package.json not found in frontend/" -ForegroundColor Red
}
Set-Location ..

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Make sure Redis is running: redis-server" -ForegroundColor White
Write-Host "  2. Initialize database: cd backend && python init_db.py" -ForegroundColor White
Write-Host "  3. Start all services: .\start-all.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Or start services manually:" -ForegroundColor Yellow
Write-Host "  Terminal 1: cd backend && python -m uvicorn app.main:app --port 8000" -ForegroundColor Gray
Write-Host "  Terminal 2: cd ai_service && python -m uvicorn app.main:app --port 8001" -ForegroundColor Gray
Write-Host "  Terminal 3: cd eda_tools && python -m uvicorn app.main:app --port 8002" -ForegroundColor Gray
Write-Host "  Terminal 4: cd backend && python start_worker.py" -ForegroundColor Gray
Write-Host "  Terminal 5: cd frontend && npm run dev" -ForegroundColor Gray
Write-Host ""
