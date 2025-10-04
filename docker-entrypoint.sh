#!/bin/bash

# Docker startup script for Nifty Analysis Application

# Create logs directory if it doesn't exist
mkdir -p /app/logs

# Function to check if dependencies are available
check_dependencies() {
    echo "Checking Python dependencies..."
    python -c "
import sys
try:
    import fastapi, uvicorn, pandas, numpy, scipy, requests, pydantic, loguru
    print('✅ Core dependencies are available')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
    sys.exit(1)
"
}

# Function to start the appropriate service
start_service() {
    local service=${1:-nse}
    
    case $service in
        "nse")
            echo "🚀 Starting NSE API..."
            exec uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
            ;;
        *)
            echo "❌ Unknown service: $service"
            echo "Available services: nse"
            exit 1
            ;;
    esac
}

# Main execution
echo "🐳 Nifty Analysis Docker Container Starting..."
echo "=============================================="

# Check dependencies
check_dependencies

# Determine service to start based on environment or argument
SERVICE=${NIFTY_SERVICE:-${1:-yahoo}}

echo "Service: $SERVICE"
echo "Python Path: $PYTHONPATH"
echo "Working Directory: $(pwd)"

# Start the service
start_service $SERVICE
