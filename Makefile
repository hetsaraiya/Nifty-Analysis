# Nifty Analysis Docker Management
.PHONY: help build up down logs clean yahoo full flask all

# Default target
help:
	@echo "🐳 Nifty Analysis Docker Commands"
	@echo "=================================="
	@echo "make build     - Build Docker image"
	@echo "make yahoo     - Start Yahoo Finance API (Port 8000)"
	@echo "make full      - Start Full API with Angel One (Port 8001)"
	@echo "make flask     - Start Flask Web App (Port 5000)"
	@echo "make all       - Start all services"
	@echo "make up        - Start all services (alias for 'all')"
	@echo "make down      - Stop all services"
	@echo "make logs      - View logs from all services"
	@echo "make logs-yahoo- View logs from Yahoo API service"
	@echo "make logs-full - View logs from Full API service"
	@echo "make logs-flask- View logs from Flask service"
	@echo "make clean     - Clean up containers and images"
	@echo "make rebuild   - Rebuild and restart services"

# Build the Docker image
build:
	@echo "🔨 Building Nifty Analysis Docker image..."
	docker-compose build

# Start Yahoo Finance API service only
yahoo:
	@echo "🚀 Starting Yahoo Finance API service..."
	docker-compose up -d nifty-yahoo-api
	@echo "✅ Yahoo Finance API started at http://localhost:8000"

# Start Full API service only
full:
	@echo "🚀 Starting Full API service..."
	docker-compose up -d nifty-full-api
	@echo "✅ Full API started at http://localhost:8001"

# Start Flask web application only
flask:
	@echo "🚀 Starting Flask web application..."
	docker-compose up -d nifty-flask-app
	@echo "✅ Flask app started at http://localhost:5000"

# Start all services
all:
	@echo "🚀 Starting all Nifty Analysis services..."
	docker-compose up -d
	@echo "✅ All services started:"
	@echo "   - Yahoo API: http://localhost:8000"
	@echo "   - Full API:  http://localhost:8001"
	@echo "   - Flask App: http://localhost:5000"

# Alias for all services
up: all

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker-compose down

# View logs from all services
logs:
	docker-compose logs -f

# View logs from specific services
logs-yahoo:
	docker-compose logs -f nifty-yahoo-api

logs-full:
	docker-compose logs -f nifty-full-api

logs-flask:
	docker-compose logs -f nifty-flask-app

# Check service status
status:
	@echo "📊 Service Status:"
	@echo "=================="
	docker-compose ps

# Clean up containers and images
clean:
	@echo "🧹 Cleaning up containers and images..."
	docker-compose down --rmi all --volumes
	docker system prune -f

# Rebuild and restart services
rebuild:
	@echo "🔄 Rebuilding and restarting services..."
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

# Development mode with live reload
dev-yahoo:
	@echo "🛠️ Starting Yahoo API in development mode..."
	docker-compose -f docker-compose.yml up nifty-yahoo-api

dev-full:
	@echo "🛠️ Starting Full API in development mode..."
	docker-compose -f docker-compose.yml up nifty-full-api

# Production deployment
prod:
	@echo "🏭 Starting production deployment..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "✅ Production services started"

# Health check
health:
	@echo "🔍 Checking service health..."
	@curl -f http://localhost:8000/health 2>/dev/null && echo "✅ Yahoo API: Healthy" || echo "❌ Yahoo API: Down"
	@curl -f http://localhost:8001/health 2>/dev/null && echo "✅ Full API: Healthy" || echo "❌ Full API: Down"
	@curl -f http://localhost:5000/health 2>/dev/null && echo "✅ Flask App: Healthy" || echo "❌ Flask App: Down"
