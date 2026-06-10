# CircuitGPT Service Status (PowerShell)
# 使用方法: .\status.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CircuitGPT Service Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查前端服务
Write-Host "[Frontend Service]" -ForegroundColor Yellow
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    $cmdLine -like "*next*dev*" -or $cmdLine -like "*npm*dev*"
}

if ($nodeProcesses) {
    Write-Host "  Status: " -NoNewline -ForegroundColor White
    Write-Host "[Running]" -ForegroundColor Green
    $nodeProcesses | ForEach-Object {
        Write-Host "  Process ID: $($_.Id)" -ForegroundColor Gray
    }
    Write-Host "  URL: http://localhost:3000" -ForegroundColor Cyan
} else {
    Write-Host "  Status: " -NoNewline -ForegroundColor White
    Write-Host "[Stopped]" -ForegroundColor Red
}

Write-Host ""

# 检查后端服务
Write-Host "[Backend Service]" -ForegroundColor Yellow
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
    $cmdLine -like "*uvicorn*" -or $cmdLine -like "*app.main*"
}

if ($pythonProcesses) {
    Write-Host "  Status: " -NoNewline -ForegroundColor White
    Write-Host "[Running]" -ForegroundColor Green
    $pythonProcesses | ForEach-Object {
        Write-Host "  Process ID: $($_.Id)" -ForegroundColor Gray
    }
    Write-Host "  URL: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
} else {
    Write-Host "  Status: " -NoNewline -ForegroundColor White
    Write-Host "[Stopped]" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Network Port Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查端口
$port3000 = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if ($port3000) {
    Write-Host "[OK] Port 3000 (Frontend) is in use" -ForegroundColor Green
} else {
    Write-Host "[X] Port 3000 (Frontend) is free" -ForegroundColor Gray
}

$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($port8000) {
    Write-Host "[OK] Port 8000 (Backend) is in use" -ForegroundColor Green
} else {
    Write-Host "[X] Port 8000 (Backend) is free" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
