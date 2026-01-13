#!/bin/bash
# AI Circuit Designer - Complete Startup Script (Linux/Mac)

echo "========================================"
echo "  AI Circuit Designer - Startup Script"
echo "========================================"
echo ""

# Check if Redis is running
echo "📋 [1/7] Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
else
    echo "⚠️  Redis is not running. Please start Redis in a separate terminal:"
    echo "   redis-server"
    echo ""
    echo "Press Enter to continue anyway (services will fail until Redis is running)..."
    read
fi

# Initialize database
echo ""
echo "📋 [2/7] Initializing database..."
cd backend
if [ -f "init_db.py" ]; then
    python3 init_db.py
    if [ $? -eq 0 ]; then
        echo "✅ Database initialized"
    else
        echo "⚠️  Database initialization had issues"
    fi
else
    echo "⚠️  init_db.py not found"
fi
cd ..

# Function to start service in background
start_service() {
    local name=$1
    local port=$2
    local dir=$3
    local cmd=$4

    echo ""
    echo "📋 Starting $name (port $port)..."
    cd "$dir"
    nohup $cmd > "../logs/${name}.log" 2>&1 &
    local pid=$!
    echo "✅ $name started (PID: $pid)"
    cd ..
    sleep 2
    echo $pid > "pids/${name}.pid"
}

# Create logs and pids directories
mkdir -p logs pids

# Start Backend API
start_service "backend-api" 8000 "backend" "python3 -m uvicorn app.main:app --reload --port 8000"

# Start AI Service
start_service "ai-service" 8001 "ai_service" "python3 -m uvicorn app.main:app --reload --port 8001"

# Start EDA Service
start_service "eda-service" 8002 "eda_tools" "python3 -m uvicorn app.main:app --reload --port 8002"

# Start Celery Worker
echo ""
echo "📋 [6/7] Starting Celery Worker..."
cd backend
nohup python3 start_worker.py > "../logs/celery-worker.log" 2>&1 &
local celery_pid=$!
echo "✅ Celery Worker started (PID: $celery_pid)"
cd ..
echo $celery_pid > "pids/celery-worker.pid"

# Start Frontend
echo ""
echo "📋 [7/7] Starting Frontend (port 3000)..."
cd frontend
if [ -d "node_modules" ]; then
    echo "✅ Frontend dependencies already installed"
else
    echo "📦 Installing frontend dependencies..."
    npm install
fi
nohup npm run dev > "../logs/frontend.log" 2>&1 &
local frontend_pid=$!
echo "✅ Frontend started (PID: $frontend_pid)"
cd ..
echo $frontend_pid > "pids/frontend.pid"

# Summary
echo ""
echo "========================================"
echo "  ✅ All Services Started Successfully!"
echo "========================================"
echo ""
echo "🌐 Access the application:"
echo "   Frontend:        http://localhost:3000"
echo "   Backend API:     http://localhost:8000/docs"
echo "   AI Service:      http://localhost:8001/docs"
echo "   EDA Service:     http://localhost:8002/docs"
echo ""
echo "📝 Logs:"
echo "   Backend API:     logs/backend-api.log"
echo "   AI Service:      logs/ai-service.log"
echo "   EDA Service:     logs/eda-service.log"
echo "   Celery Worker:   logs/celery-worker.log"
echo "   Frontend:        logs/frontend.log"
echo ""
echo "🛑 To stop all services, run: ./stop-all.sh"
echo ""

# Wait for user input
echo "Press Ctrl+C to stop monitoring (services will continue running in background)"
trap "echo ''; echo 'Monitoring stopped. Services are still running.'; exit 0" SIGINT

while true; do
    sleep 5
done
