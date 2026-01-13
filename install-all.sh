#!/bin/bash
# AI Circuit Designer - Complete Installation Script (Linux/Mac)

echo "========================================"
echo "  AI Circuit Designer - Installation"
echo "========================================"
echo ""

# Check Python
echo "📋 [1/6] Checking Python installation..."
if command -v python3 &> /dev/null; then
    python3_version=$(python3 --version)
    echo "✅ Python found: $python3_version"
else
    echo "❌ Python 3 not found"
    echo "Please install Python 3.10+ from: https://www.python.org/"
    exit 1
fi

# Check Node.js
echo ""
echo "📋 [2/6] Checking Node.js installation..."
if command -v node &> /dev/null; then
    node_version=$(node --version)
    echo "✅ Node.js found: $node_version"
else
    echo "❌ Node.js not found"
    echo "Please install Node.js 18+ from: https://nodejs.org/"
    exit 1
fi

# Check Redis
echo ""
echo "📋 [3/6] Checking Redis installation..."
if command -v redis-cli &> /dev/null; then
    redis_version=$(redis-cli --version)
    echo "✅ Redis found: $redis_version"
else
    echo "⚠️  Redis not found"
    echo "   Please install Redis from: https://redis.io/download"
    echo "   Mac: brew install redis"
    echo "   Ubuntu: sudo apt-get install redis-server"
fi

# Install Backend dependencies
echo ""
echo "📦 [4/6] Installing Backend dependencies..."
cd backend
if [ -f "requirements.txt" ]; then
    echo "   Installing: requirements.txt"
    python3 -m pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "✅ Backend dependencies installed"
    else
        echo "⚠️  Backend installation had issues"
    fi
else
    echo "❌ requirements.txt not found in backend/"
fi
cd ..

# Install AI Service dependencies
echo ""
echo "📦 [5/6] Installing AI Service dependencies..."
cd ai_service
if [ -f "requirements.txt" ]; then
    echo "   Installing: requirements.txt"
    python3 -m pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "✅ AI Service dependencies installed"
    else
        echo "⚠️  AI Service installation had issues"
    fi
else
    echo "❌ requirements.txt not found in ai_service/"
fi
cd ..

# Install EDA Tools dependencies
echo ""
echo "📦 [6/6] Installing EDA Tools dependencies..."
cd eda_tools
if [ -f "requirements.txt" ]; then
    echo "   Installing: requirements.txt"
    python3 -m pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "✅ EDA Tools dependencies installed"
    else
        echo "⚠️  EDA Tools installation had issues"
    fi
else
    echo "❌ requirements.txt not found in eda_tools/"
fi
cd ..

# Install Frontend dependencies
echo ""
echo "📦 [7/7] Installing Frontend dependencies..."
cd frontend
if [ -f "package.json" ]; then
    echo "   Installing: npm dependencies"
    npm install
    if [ $? -eq 0 ]; then
        echo "✅ Frontend dependencies installed"
    else
        echo "⚠️  Frontend installation had issues"
    fi
else
    echo "❌ package.json not found in frontend/"
fi
cd ..

# Make scripts executable
chmod +x start-all.sh stop-all.sh

# Summary
echo ""
echo "========================================"
echo "  ✅ Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Make sure Redis is running: redis-server"
echo "  2. Initialize database: cd backend && python3 init_db.py"
echo "  3. Start all services: ./start-all.sh"
echo ""
echo "Or start services manually:"
echo "  Terminal 1: cd backend && python3 -m uvicorn app.main:app --port 8000"
echo "  Terminal 2: cd ai_service && python3 -m uvicorn app.main:app --port 8001"
echo "  Terminal 3: cd eda_tools && python3 -m uvicorn app.main:app --port 8002"
echo "  Terminal 4: cd backend && python3 start_worker.py"
echo "  Terminal 5: cd frontend && npm run dev"
echo ""
