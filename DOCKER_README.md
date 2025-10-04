# Nifty Analysis - Docker Deployment Guide

This document provides instructions for running the Nifty Analysis application using Docker.

## Quick Start

### 1. Prerequisites
- Docker and Docker Compose installed

### 2. Environment Setup
```bash
# Copy the environment template
cp .env.example .env

# Edit .env file with your credentials (optional)
nano .env
```

### 3. Run with Docker Compose

#### Start the API Service
```bash
# Start the API service
docker-compose up nifty-api

# Access at: http://localhost:8000
```

#### All Services
```bash
# Start all services
docker-compose up -d

# Services will be available at:
# - Yahoo API: http://localhost:8000
# - Full API: http://localhost:8001  
# - Flask App: http://localhost:5000
```

## Docker Commands

### Build and Run
```bash
# Build the Docker image
docker build -t nifty-analysis .

# Run Yahoo Finance API
docker run -p 8000:8000 nifty-analysis

# Run with environment variables
docker run -p 8000:8000 --env-file .env nifty-analysis
```

### Management Commands
```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs nifty-api
docker-compose logs -f  # Follow logs

# Stop services
docker-compose down

# Rebuild services
docker-compose up --build
```

## API Endpoints

### API Service (Port 8000)
- `GET /` - Web interface
- `GET /api/status` - Service status
- `POST /api/options-chain` - Generate options chain
- `POST /api/calculate-implied-volatility` - Calculate IV
- `POST /api/portfolio-greeks` - Portfolio Greeks

## Environment Variables

### Optional Configuration
```bash
SECRET_KEY=your-secret-key
FLASK_DEBUG=false
CACHE_TIMEOUT=300
LOG_LEVEL=INFO
```

## Production Deployment

### Using Docker Compose (Recommended)
```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# With custom environment
docker-compose --env-file .env.production up -d
```

### Using Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml nifty-analysis
```

### Using Kubernetes
```bash
# Generate Kubernetes manifests
komose convert -f docker-compose.yml

# Apply to cluster
kubectl apply -f nifty-analysis-*.yaml
```

## Volumes and Data Persistence

The application uses volumes for:
- `./logs:/app/logs` - Application logs
- `./templates:/app/templates` - Flask templates (Flask service only)

## Health Checks

Check service health:
```bash
# Yahoo Finance API
curl http://localhost:8000/health

# Full API
curl http://localhost:8001/health

# Flask App
curl http://localhost:5000/health
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Change port mappings in docker-compose.yml
2. **Permission issues**: Ensure proper file permissions
3. **API credentials**: Verify Angel One credentials in .env file

### Logs
```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs nifty-yahoo-api

# Follow logs in real-time
docker-compose logs -f nifty-yahoo-api
```

### Container Shell Access
```bash
# Access running container
docker-compose exec nifty-yahoo-api bash

# Or for debugging
docker run -it --entrypoint bash nifty-analysis
```

## Performance Optimization

### For Production
- Use multi-stage builds for smaller images
- Implement proper logging rotation
- Configure resource limits
- Use external database for persistence
- Set up monitoring and alerting

### Resource Limits
```yaml
# Add to docker-compose.yml under each service
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
```

## Security Considerations

1. **Environment Variables**: Never commit .env files with real credentials
2. **Network Security**: Use Docker networks to isolate services
3. **User Permissions**: Application runs as non-root user
4. **API Keys**: Rotate API keys regularly
5. **HTTPS**: Use reverse proxy (nginx/traefik) for HTTPS in production
