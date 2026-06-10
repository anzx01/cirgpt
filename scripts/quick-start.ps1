# CircuitGPT Quick Start (PowerShell)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   CircuitGPT Quick Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Checking environment..." -ForegroundColor Yellow

# Check frontend
if (Test-Path "..\frontend\node_modules") {
    Write-Host "[OK] Frontend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "[X] Frontend dependencies missing" -ForegroundColor Red
    Write-Host "    Run: cd frontend && npm install" -ForegroundColor Gray
    exit 1
}

# Check backend
if (Test-Path "..\backend\.env") {
    Write-Host "[OK] Backend configuration exists" -ForegroundColor Green
} else {
    Write-Host "[X] Backend .env missing" -ForegroundColor Red
    Write-Host "    See: backend\CONFIG_SETUP.md" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start backend
Write-Host "[1/2] Starting backend on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd ..\backend; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -WindowStyle Normal
Start-Sleep -Seconds 3

# Start frontend
Write-Host "[2/2] Starting frontend on port 3000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd ..\frontend; npm run dev" -WindowStyle Normal
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Services Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor White
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Press any key to exit (services will continue running)..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
