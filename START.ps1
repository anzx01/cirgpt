# CircuitGPT Simple Start
# Usage: Right-click -> Run with PowerShell

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CircuitGPT Starting..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check frontend
$frontendPath = Join-Path $scriptDir "frontend"
if (-not (Test-Path $frontendPath)) {
    Write-Host "[ERROR] Frontend directory not found: $frontendPath" -ForegroundColor Red
    Write-Host "Press Enter to exit..." -ForegroundColor Gray
    Read-Host
    exit 1
}

# Check backend
$backendPath = Join-Path $scriptDir "backend"
if (-not (Test-Path $backendPath)) {
    Write-Host "[ERROR] Backend directory not found: $backendPath" -ForegroundColor Red
    Write-Host "Press Enter to exit..." -ForegroundColor Gray
    Read-Host
    exit 1
}

# Start backend
Write-Host "[1/2] Starting backend on port 8000..." -ForegroundColor Yellow
$backendCmd = "Set-Location '$backendPath'; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
Start-Sleep -Seconds 3

# Start frontend
Write-Host "[2/2] Starting frontend on port 3000..." -ForegroundColor Yellow
$frontendCmd = "Set-Location '$frontendPath'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
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
Write-Host "Opening browser in 3 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 3
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Services are running in separate windows." -ForegroundColor Gray
Write-Host "Close those windows or run STOP.ps1 to stop services." -ForegroundColor Gray
Write-Host ""
Write-Host "Press Enter to exit this window..." -ForegroundColor Gray
Read-Host
