#!/bin/bash
# Stop All Services Script (Linux/Mac)

echo "🛑 Stopping all AI Circuit Designer services..."

# Stop services using PID files
if [ -d "pids" ]; then
    for pid_file in pids/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            name=$(basename "$pid_file" .pid)
            if ps -p $pid > /dev/null 2>&1; then
                echo "  Stopping $name (PID: $pid)..."
                kill $pid 2>/dev/null || kill -9 $pid 2>/dev/null
            fi
            rm "$pid_file"
        fi
    done
fi

# Also kill by process name (fallback)
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "start_worker.py" 2>/dev/null
pkill -f "npm run dev" 2>/dev/null

echo "✅ All services stopped"
echo ""
echo "Note: Redis continues running. Stop it manually with:"
echo " redis-cli shutdown"
echo " or: pkill redis-server"
