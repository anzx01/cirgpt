# CircuitGPT Stop All Services
# Usage: Right-click -> Run with PowerShell

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Stopping CircuitGPT Services..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop Node.js processes (Frontend)
Write-Host "[1/2] Stopping frontend..." -ForegroundColor Yellow
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $nodeProcesses | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Frontend stopped" -ForegroundColor Green
} else {
    Write-Host "  No frontend process found" -ForegroundColor Gray
}

# Stop Python processes (Backend)
Write-Host "[2/2] Stopping backend..." -ForegroundColor Yellow
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $stopped = $false
    $pythonProcesses | ForEach-Object {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -like "*uvicorn*" -or $cmdLine -like "*app.main*") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }
    if ($stopped) {
        Write-Host "  Backend stopped" -ForegroundColor Green
    } else {
        Write-Host "  No backend process found" -ForegroundColor Gray
    }
} else {
    Write-Host "  No backend process found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All Services Stopped!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Enter to exit..." -ForegroundColor Gray
Read-Host
