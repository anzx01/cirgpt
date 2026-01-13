# AI Circuit Designer - Complete Startup Script
# PowerShell script to start all services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI Circuit Designer - Startup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Redis is running
Write-Host "📋 [1/7] Checking Redis..." -ForegroundColor Yellow
try {
    $redisProcess = Get-Process -Name redis -ErrorAction SilentlyContinue
    if ($redisProcess) {
        Write-Host "✅ Redis is already running" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Redis is not running. Please start Redis in a separate terminal:" -ForegroundColor Red
        Write-Host "   redis-server" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Press Enter to continue anyway (services will fail until Redis is running)..."
        Read-Host
    }
} catch {
    Write-Host "⚠️  Could not check Redis status" -ForegroundColor Red
}

# Initialize database
Write-Host ""
Write-Host "📋 [2/7] Initializing database..." -ForegroundColor Yellow
Set-Location backend
if (Test-Path "init_db.py") {
    python init_db.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Database initialized" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Database initialization had issues" -ForegroundColor Red
    }
} else {
    Write-Host "⚠️  init_db.py not found" -ForegroundColor Red
}
Set-Location ..

# Start Backend API
Write-Host ""
Write-Host "📋 [3/7] Starting Backend API (port 8000)..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" -WorkingDirectory "backend" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "✅ Backend API started (PID: $($backendProcess.Id))" -ForegroundColor Green

# Start AI Service
Write-Host ""
Write-Host "📋 [4/7] Starting AI Service (port 8001)..." -ForegroundColor Yellow
$aiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8001" -WorkingDirectory "ai_service" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "✅ AI Service started (PID: $($aiProcess.Id))" -ForegroundColor Green

# Start EDA Service
Write-Host ""
Write-Host "📋 [5/7] Starting EDA Service (port 8002)..." -ForegroundColor Yellow
$edaProcess = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8002" -WorkingDirectory "eda_tools" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "✅ EDA Service started (PID: $($edaProcess.Id))" -ForegroundColor Green

# Start Celery Worker
Write-Host ""
Write-Host "📋 [6/7] Starting Celery Worker..." -ForegroundColor Yellow
$celeryProcess = Start-Process -FilePath "python" -ArgumentList "start_worker.py" -WorkingDirectory "backend" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 2
Write-Host "✅ Celery Worker started (PID: $($celeryProcess.Id))" -ForegroundColor Green

# Start Frontend
Write-Host ""
Write-Host "📋 [7/7] Starting Frontend (port 3000)..." -ForegroundColor Yellow
Set-Location frontend
if (Test-Path "node_modules") {
    Write-Host "✅ Frontend dependencies already installed" -ForegroundColor Green
} else {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -WindowStyle Normal
Set-Location ..
Write-Host "✅ Frontend started (PID: $($frontendProcess.Id))" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ All Services Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 Access the application:" -ForegroundColor Yellow
Write-Host "   Frontend:        http://localhost:3000" -ForegroundColor White
Write-Host "   Backend API:     http://localhost:8000/docs" -ForegroundColor White
Write-Host "   AI Service:      http://localhost:8001/docs" -ForegroundColor White
Write-Host "   EDA Service:     http://localhost:8002/docs" -ForegroundColor White
Write-Host ""
Write-Host "📝 Process IDs:" -ForegroundColor Yellow
Write-Host "   Backend API:     $($backendProcess.Id)" -ForegroundColor White
Write-Host "   AI Service:      $($aiProcess.Id)" -ForegroundColor White
Write-Host "   EDA Service:     $($edaProcess.Id)" -ForegroundColor White
Write-Host "   Celery Worker:   $($celeryProcess.Id)" -ForegroundColor White
Write-Host "   Frontend:        $($frontendProcess.Id)" -ForegroundColor White
Write-Host ""
Write-Host "🛑 To stop all services, run: .\stop-all.ps1" -ForegroundColor Yellow
Write-Host ""

# Keep script running or exit
Write-Host "Press Ctrl+C to stop monitoring (services will continue running in background)" -ForegroundColor Gray
Write-Host ""

# Monitor processes
try {
    while ($true) {
        Start-Sleep -Seconds 5
        # Check if any process died
        $processes = @($backendProcess, $aiProcess, $edaProcess, $celeryProcess, $frontendProcess)
        $deadProcesses = $processes | Where-Object { $_.HasExited }

        if ($deadProcesses) {
            foreach ($proc in $deadProcesses) {
                Write-Host "⚠️  Process $($proc.Id) has exited" -ForegroundColor Red
            }
        }
    }
} catch [System.Management.Automation.PipelineStoppedException] {
    Write-Host ""
    Write-Host "Monitoring stopped. Services are still running." -ForegroundColor Yellow
}
