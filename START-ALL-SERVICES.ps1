# CircuitGPT Complete Startup Script
# Starts all 4 services in order

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CircuitGPT Complete System Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Service 1: Backend Gateway (Port 8000)
Write-Host "[1/4] Starting Backend Gateway (port 8000)..." -ForegroundColor Yellow
$backendPath = Join-Path $scriptDir "backend"
$backendCmd = "Set-Location '$backendPath'; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
Start-Sleep -Seconds 3

# Service 2: AI Service (Port 8001)
Write-Host "[2/4] Starting AI Service (port 8001)..." -ForegroundColor Yellow
$aiPath = Join-Path $scriptDir "ai_service"
$aiCmd = "Set-Location '$aiPath'; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $aiCmd -WindowStyle Normal
Start-Sleep -Seconds 3

# Service 3: EDA Service (Port 8002)
Write-Host "[3/4] Starting EDA Service (port 8002)..." -ForegroundColor Yellow
$edaPath = Join-Path $scriptDir "eda_tools"
$edaCmd = "Set-Location '$edaPath'; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $edaCmd -WindowStyle Normal
Start-Sleep -Seconds 3

# Service 4: Frontend (Port 3000)
Write-Host "[4/4] Starting Frontend (port 3000)..." -ForegroundColor Yellow
$frontendPath = Join-Path $scriptDir "frontend"
$frontendCmd = "Set-Location '$frontendPath'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All Services Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor White
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor Cyan
Write-Host "  AI Service: http://localhost:8001" -ForegroundColor Cyan
Write-Host "  EDA Service: http://localhost:8002" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "All services are running in separate windows." -ForegroundColor Gray
Write-Host "To stop all services, run: .\STOP-ALL-SERVICES.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Enter to exit this window..." -ForegroundColor Gray
Read-Host
