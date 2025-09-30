#!/bin/bash
# Start script for NIFTY Options Greeks Analyzer with NSE India Data

echo "🚀 Starting NIFTY Options Greeks Analyzer - NSE India Edition"
echo "=============================================================="

# Check if required packages are installed
echo "📦 Checking dependencies..."
python3 -c "import fastapi, uvicorn, pandas, numpy, scipy, requests, loguru" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Installing..."
    pip install -q fastapi uvicorn pandas numpy scipy requests loguru pydantic jinja2
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
    echo "✅ Dependencies installed successfully"
else
    echo "✅ All dependencies found"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the FastAPI server
echo ""
echo "🌐 Starting server..."
echo "Dashboard will be available at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 -m uvicorn fastapi_nse:app --host 0.0.0.0 --port 8000 --reload --log-level info
