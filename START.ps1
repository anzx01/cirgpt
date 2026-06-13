# CircuitGPT full local start
# Usage: Right-click -> Run with PowerShell

$ErrorActionPreference = "Stop"

function Test-TcpPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $result = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }
        $client.EndConnect($result)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Start-ServiceProcess {
    param(
        [string]$Name,
        [string]$Path,
        [string]$Command,
        [int]$Port
    )

    if (Test-TcpPort -Port $Port) {
        Write-Host "[OK] $Name already listening on port $Port" -ForegroundColor Green
        return
    }

    Write-Host "Starting $Name on port $Port..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Path'; $Command" -WindowStyle Hidden
    Start-Sleep -Seconds 3

    if (Test-TcpPort -Port $Port) {
        Write-Host "[OK] $Name started" -ForegroundColor Green
    } else {
        Write-Host "[WARN] $Name is not responding yet; it may still be starting" -ForegroundColor Yellow
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CircuitGPT Starting..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $scriptDir "backend"
$aiPath = Join-Path $scriptDir "ai_service"
$edaPath = Join-Path $scriptDir "eda_tools"
$frontendPath = Join-Path $scriptDir "frontend"

$requiredPaths = @(
    $backendPath,
    (Join-Path $backendPath "venv\Scripts\python.exe"),
    $aiPath,
    (Join-Path $aiPath "venv\Scripts\python.exe"),
    $edaPath,
    (Join-Path $edaPath "venv\Scripts\python.exe"),
    $frontendPath
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path $path)) {
        Write-Host "[ERROR] Required path not found: $path" -ForegroundColor Red
        Write-Host "Press Enter to exit..." -ForegroundColor Gray
        Read-Host
        exit 1
    }
}

Start-ServiceProcess -Name "Backend API" -Path $backendPath -Command ".\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -Port 8000
Start-ServiceProcess -Name "AI Service" -Path $aiPath -Command ".\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001" -Port 8001
Start-ServiceProcess -Name "EDA Service" -Path $edaPath -Command ".\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8002" -Port 8002
Start-ServiceProcess -Name "Frontend" -Path $frontendPath -Command "npm run dev" -Port 3000

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Services Started" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor White
Write-Host "  Frontend:    http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend API: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  AI Service:  http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "  EDA Service: http://localhost:8002/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services are running in the background. Run STOP.ps1 to stop them." -ForegroundColor Gray
Write-Host ""
Write-Host "Press Enter to exit this window..." -ForegroundColor Gray
Read-Host
