# Stop All Services Script
Write-Host "🛑 Stopping all AI Circuit Designer services..." -ForegroundColor Yellow

# Kill all relevant processes
$processNames = @("python", "node", "uvicorn", "npm", "pnpm")

foreach ($name in $processNames) {
    $processes = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($processes) {
        foreach ($proc in $processes) {
            # Check if it's our service by examining command line
            try {
                $cmd = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
                if ($cmd -match "cirgpt" -or $cmd -match "uvicorn.*app.main" -or $cmd -match "npm.*dev") {
                    Write-Host "  Stopping $($name) (PID: $($proc.Id))..." -ForegroundColor Gray
                    Stop-Process -Id $proc.Id -Force
                }
            } catch {
                # If we can't check command line, skip it
            }
        }
    }
}

Write-Host "✅ All services stopped" -ForegroundColor Green
Write-Host ""
Write-Host "Note: Redis continues running. Stop it manually with:" -ForegroundColor Gray
Write-Host " redis-cli shutdown" -ForegroundColor Gray
