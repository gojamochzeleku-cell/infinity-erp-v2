#!/bin/bash
echo "=========================================="
echo "🚀 STARTING INFINITY ERP v2"
echo "=========================================="

# Activate virtual environment if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    source venv/bin/activate
fi

# Check if port 8000 is already in use
if lsof -i :8000 > /dev/null 2>&1; then
    echo "⚠️  Port 8000 is already in use. Stopping existing process..."
    pkill -f uvicorn
    sleep 2
fi

echo "Starting Uvicorn server in the background..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > erp.log 2>&1 &
sleep 3

# Check if it started
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health | grep -q "200"; then
    echo "✅ Infinity ERP is running successfully!"
    echo "👉 Access it at: http://127.0.0.1:8000"
    echo "👉 View logs with: tail -f erp.log"
    echo "👉 Stop server with: pkill -f uvicorn"
else
    echo "❌ Failed to start. Check erp.log for details."
fi
echo "=========================================="
