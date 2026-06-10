# CircuitGPT Stop All Services (PowerShell)
# 使用方法: .\stop-all.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CircuitGPT Stop All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "[1/2] Stopping frontend service..." -ForegroundColor Yellow

# 停止前端 (Node.js)
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $nodeProcesses | ForEach-Object {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdLine -like "*next*dev*" -or $cmdLine -like "*npm*dev*") {
            Write-Host "  Stopping Node.js process: $($_.Id)" -ForegroundColor Gray
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "[OK] Frontend service stopped" -ForegroundColor Green
} else {
    Write-Host "[INFO] No frontend service running" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[2/2] Stopping backend service..." -ForegroundColor Yellow

# 停止后端 (Python/uvicorn)
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $pythonProcesses | ForEach-Object {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdLine -like "*uvicorn*" -or $cmdLine -like "*app.main*") {
            Write-Host "  Stopping Python process: $($_.Id)" -ForegroundColor Gray
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "[OK] Backend service stopped" -ForegroundColor Green
} else {
    Write-Host "[INFO] No backend service running" -ForegroundColor Gray
}

# 清理PID文件
$pidDir = Join-Path $scriptDir ".pids"
if (Test-Path $pidDir) {
    Remove-Item -Path "$pidDir\*.pid" -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All Services Stopped" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
