#!/bin/bash

# NIFTY Options Greeks Calculator - Yahoo Finance Edition
# FastAPI Application Startup Script

echo "🚀 Starting NIFTY Options Greeks Calculator (Yahoo Finance Edition)"
echo "================================================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python version: $python_version"

# Create logs directory if it doesn't exist
mkdir -p logs
echo "✅ Logs directory created/verified"

# Install dependencies
echo "📦 Installing/updating dependencies..."
python3 -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed successfully"

# Test the Yahoo Finance connection
echo "🔌 Testing Yahoo Finance connection..."
python3 -c "
from yahoo_nifty_greeks import YahooFinanceAPI
api = YahooFinanceAPI()
price = api.get_nifty_price()
if price:
    print(f'✅ Yahoo Finance connection successful - NIFTY: ₹{price}')
else:
    print('⚠️  Yahoo Finance connection test failed, but the app will still work')
"

# Start the FastAPI application
echo ""
echo "🌟 Starting FastAPI application..."
echo "📊 Dashboard will be available at: http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo "🔄 API Alternative Docs: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo "================================================================"

# Start the application
python3 -m uvicorn fastapi_yahoo:app --host 0.0.0.0 --port 8000 --reload
