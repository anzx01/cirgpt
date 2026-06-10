# CircuitGPT Stop All Services (Complete)
# Stops all 4 services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Stopping All CircuitGPT Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop Frontend (Node.js)
Write-Host "[1/4] Stopping Frontend..." -ForegroundColor Yellow
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $nodeProcesses | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Frontend stopped" -ForegroundColor Green
} else {
    Write-Host "  No frontend process found" -ForegroundColor Gray
}

# Stop Backend, AI, and EDA (Python/uvicorn)
Write-Host "[2/4] Stopping Backend Gateway..." -ForegroundColor Yellow
Write-Host "[3/4] Stopping AI Service..." -ForegroundColor Yellow
Write-Host "[4/4] Stopping EDA Service..." -ForegroundColor Yellow

$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $stopped = @{
        backend = $false
        ai = $false
        eda = $false
    }

    $pythonProcesses | ForEach-Object {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -like "*app.main:app*8000*") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            $stopped.backend = $true
        }
        elseif ($cmdLine -like "*app.main:app*8001*") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            $stopped.ai = $true
        }
        elseif ($cmdLine -like "*app.main:app*8002*") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            $stopped.eda = $true
        }
    }

    if ($stopped.backend) { Write-Host "  Backend Gateway stopped" -ForegroundColor Green }
    else { Write-Host "  No backend process found" -ForegroundColor Gray }

    if ($stopped.ai) { Write-Host "  AI Service stopped" -ForegroundColor Green }
    else { Write-Host "  No AI service process found" -ForegroundColor Gray }

    if ($stopped.eda) { Write-Host "  EDA Service stopped" -ForegroundColor Green }
    else { Write-Host "  No EDA service process found" -ForegroundColor Gray }
} else {
    Write-Host "  No Python processes found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All Services Stopped!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Enter to exit..." -ForegroundColor Gray
Read-Host
