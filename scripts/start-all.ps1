# CircuitGPT Start All Services (PowerShell)
# 使用方法: .\start-all.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CircuitGPT Full Service Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 启动后端
Write-Host "[1/3] Starting backend service..." -ForegroundColor Yellow
Write-Host ""
Start-Process -FilePath "cmd.exe" -ArgumentList "/c start-backend.bat" -WorkingDirectory $scriptDir -WindowStyle Normal

# 等待5秒
Start-Sleep -Seconds 5

# 启动前端
Write-Host ""
Write-Host "[2/3] Starting frontend service..." -ForegroundColor Yellow
Write-Host ""
Start-Process -FilePath "cmd.exe" -ArgumentList "/c start-frontend.bat" -WorkingDirectory $scriptDir -WindowStyle Normal

# 等待5秒
Start-Sleep -Seconds 5

# 检查状态
Write-Host ""
Write-Host "[3/3] Checking service status..." -ForegroundColor Yellow
Write-Host ""

try {
    $backend = Invoke-WebRequest -Uri "http://localhost:8000/" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($backend) {
        Write-Host "[OK] Backend running: http://localhost:8000" -ForegroundColor Green
    }
} catch {
    Write-Host "[X] Backend not responding" -ForegroundColor Red
}

try {
    $frontend = Invoke-WebRequest -Uri "http://localhost:3000/" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($frontend) {
        Write-Host "[OK] Frontend running: http://localhost:3000" -ForegroundColor Green
    }
} catch {
    Write-Host "[X] Frontend not responding (may still be starting)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Startup Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor White
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  Backend: http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "To stop services:" -ForegroundColor White
Write-Host "  Run .\stop-all.ps1 or stop-all.bat" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
