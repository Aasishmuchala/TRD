# God's Eye Deployment Guide

Complete containerized deployment infrastructure for God's Eye multi-agent market simulation.

## Files Created

### Backend
- **Dockerfile**: Multi-stage Python 3.11 slim image with gunicorn + uvicorn workers
- **.dockerignore**: Excludes build artifacts, caches, and test files
- **app/logging_config.py**: Structured JSON logging for production (stdout-based)

### Frontend
- **Dockerfile**: Multi-stage Node.js build + nginx production image
- **.dockerignore**: Excludes node_modules and build artifacts
- **nginx.conf**: Reverse proxy with WebSocket support, SPA routing, gzip compression, static asset caching

### Orchestration
- **docker-compose.yml**: Full stack orchestration with health checks, volumes, and environment configuration

### Reference
- **.env.example**: Configuration template with all available options

## Quick Start

### 1. Environment Setup

```bash
cd /sessions/gifted-hopeful-wozniak/mnt/TRD/gods-eye
cp .env.example .env
```

Edit `.env` with your actual values:
```bash
LLM_API_KEY=your-openai-api-key
GODS_EYE_CORS_ORIGINS=http://localhost,http://localhost:80
```

### 2. Build and Start Services

```bash
docker-compose up -d
```

This will:
- Build backend Docker image (Python 3.11 + FastAPI + Gunicorn)
- Build frontend Docker image (Node.js + React + Nginx)
- Start PostgreSQL-compatible services with persistent volumes
- Configure health checks for graceful startup sequencing

### 3. Verify Deployment

```bash
# Check all services running
docker-compose ps

# Check health endpoint
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2026-03-30T12:00:00",
  "model": "o4-mini",
  "environment": "production",
  "database": {
    "status": "connected",
    "path": "/app/data/gods_eye.db",
    "size_mb": 0.5
  },
  "llm_provider": "openai",
  "learning_enabled": true,
  "mock_mode": false
}
```

### 4. Access Application

- **Frontend**: http://localhost (Nginx proxy)
- **Backend API**: http://localhost:8000/api
- **WebSocket**: ws://localhost:8000/api/simulate/stream

## Architecture

### Backend Container
```
Python 3.11 slim
├── FastAPI application
├── Gunicorn (4 workers)
├── Uvicorn ASGI servers
├── SQLite database (/app/data)
└── Structured JSON logging to stdout
```

**Port**: 8000
**Health Check**: GET /api/health (30s interval)

### Frontend Container
```
Node 20 Alpine (build stage)
└── Nginx Alpine (production stage)
    ├── React SPA (dist/)
    ├── API proxy to backend:8000
    ├── WebSocket upgrade support
    ├── Gzip compression
    ├── Static asset caching (30d)
    └── SPA routing (try_files /index.html)
```

**Port**: 80

### Networking
- Internal Docker network for backend↔frontend communication
- Backend accessible as `http://backend:8000` from frontend nginx
- Frontend reverse proxies `/api/*` requests to backend

### Volumes
- **db-data**: Persistent SQLite database storage
- **skills-data**: Auto-learned agent skills directory

## Configuration

### Environment Variables

#### LLM Settings
- `GODS_EYE_LLM_PROVIDER`: "openai", "nous", or "custom"
- `LLM_API_KEY`: API key for chosen provider
- `GODS_EYE_MODEL`: Model identifier (e.g., "o4-mini", "gpt-4")

#### Server Settings
- `GODS_EYE_ENV`: "development" or "production"
- `GODS_EYE_LOG_LEVEL`: "debug", "info", "warning", "error"
- `GODS_EYE_CORS_ORIGINS`: Comma-separated allowed origins

#### Features
- `GODS_EYE_LEARNING`: "true" or "false" (auto-learning system)
- `GODS_EYE_MOCK`: "true" or "false" (mock LLM responses for testing)

#### Paths
- `GODS_EYE_DB_PATH`: SQLite database path (default: /app/data/gods_eye.db)

## Logging

### Production Logging (JSON to stdout)

When `GODS_EYE_ENV=production`, all logs are emitted as structured JSON:

```json
{
  "timestamp": "2026-03-30T12:00:00.000Z",
  "level": "INFO",
  "logger": "app.engine.orchestrator",
  "message": "Starting simulation with market data..."
}
```

This enables:
- Log aggregation (ELK, Datadog, CloudWatch)
- Structured searching and filtering
- Automatic parsing by log processors

### Development Logging (Human-readable text)

When `GODS_EYE_ENV=development`, logs use readable format:
```
2026-03-30 12:00:00,000 [INFO] app.engine.orchestrator: Starting simulation...
```

## Health Checks

### Endpoint: GET /api/health

**Purpose**: Docker health check + infrastructure monitoring

**Response Fields**:
- `status`: "healthy" or "degraded"
- `version`: API version (2.0.0)
- `timestamp`: ISO 8601 timestamp
- `environment`: Current environment (development/production)
- `model`: Active LLM model
- `llm_provider`: LLM provider name
- `learning_enabled`: Boolean auto-learning status
- `mock_mode`: Boolean mock LLM status
- `database`: Database connectivity info
  - `status`: "connected", "not_initialized", or "error"
  - `path`: SQLite database path
  - `size_mb`: Database file size
  - `error`: Error message if applicable

## Scaling & Production Deployment

### Gunicorn Workers
The backend runs 4 gunicorn workers. Adjust in Dockerfile:
```dockerfile
CMD ["gunicorn", "run:app", "-w", "8", ...]  # Increase workers
```

### Reverse Proxy
For production, add an external reverse proxy (Nginx, HAProxy, AWS ALB):
```nginx
upstream backend {
    server god-eye-backend:8000;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Database
SQLite works for development/small deployments. For production:
- Migrate to PostgreSQL (update DATABASE_PATH + connection string)
- Use managed services (RDS, CloudSQL)
- Configure backups and replication

### API Rate Limiting
Current limits (configurable in code):
- `/api/simulate`: 10 requests per minute
- `/api/auth/login`: 5 requests per minute
- `/api/auth/poll`: 30 requests per minute

## Troubleshooting

### Container won't start
```bash
docker-compose logs backend
docker-compose logs frontend
```

### Health check failing
```bash
# Check database file exists
docker exec gods-eye-backend ls -la /app/data/

# Test database connectivity manually
docker exec gods-eye-backend sqlite3 /app/data/gods_eye.db "SELECT 1;"
```

### WebSocket connection issues
- Verify nginx.conf has `proxy_http_version 1.1` and `Upgrade`/`Connection` headers
- Check browser DevTools Network tab for 101 Switching Protocols response

### Frontend can't reach backend
- Verify backend is healthy: `curl http://localhost:8000/api/health`
- Check frontend nginx logs: `docker logs gods-eye-frontend`
- Verify docker-compose network: `docker network ls`

## File Structure

```
gods-eye/
├── docker-compose.yml           # Orchestration
├── .env.example                 # Configuration template
├── DEPLOYMENT.md                # This file
├── backend/
│   ├── Dockerfile               # Backend image
│   ├── .dockerignore            # Build exclusions
│   ├── requirements.txt          # Python dependencies
│   ├── run.py                   # FastAPI entry point (updated)
│   ├── app/
│   │   ├── config.py            # Configuration loading
│   │   ├── logging_config.py    # Structured logging (new)
│   │   ├── api/
│   │   │   └── routes.py        # API routes (health endpoint enhanced)
│   │   └── ...
│   └── ...
└── frontend/
    ├── Dockerfile               # Frontend image
    ├── .dockerignore            # Build exclusions
    ├── nginx.conf               # Nginx configuration (new)
    ├── package.json             # Node dependencies
    ├── vite.config.js           # Vite build config
    └── src/
        └── ...
```

## Maintenance

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop Services
```bash
docker-compose down
```

### Clear Data (⚠️ Destructive)
```bash
docker-compose down -v  # Also removes volumes
```

### Update Code
```bash
# After code changes
docker-compose up -d --build
```

## Next Steps

1. **CI/CD Integration**: Add GitHub Actions to build and push images to registry
2. **Kubernetes Deployment**: Create deployment manifests for production clusters
3. **Monitoring**: Add Prometheus metrics and Grafana dashboards
4. **Security**: Enable TLS/HTTPS, implement API authentication
5. **Database Migration**: Move from SQLite to PostgreSQL for production
