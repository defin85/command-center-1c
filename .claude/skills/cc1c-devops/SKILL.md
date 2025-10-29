---
name: cc1c-devops
description: "Execute DevOps tasks for CommandCenter1C: start/stop services with Docker Compose, check health endpoints, view logs, run migrations, build Docker images. Use when user needs to start development environment, check service status, debug deployment issues, or mentions docker, compose, health checks, logs."
allowed-tools: ["Bash", "Read"]
---

# cc1c-devops

## Purpose

Управлять DevOps операциями для локальной разработки и deployment проекта CommandCenter1C.

## When to Use

Используй этот skill когда:
- Запуск/остановка локального окружения
- Проверка статуса сервисов
- Просмотр логов
- Проблемы с Docker/Docker Compose
- Пользователь упоминает: docker, compose, logs, health, start, stop, restart, build

## Quick Start Commands

### Essential Commands (Makefile)

```bash
# Start all services
make dev

# Stop all services
make stop

# View logs (all services)
make logs

# View logs (specific service)
make logs-api          # API Gateway
make logs-orchestrator # Django Orchestrator
make logs-worker       # Go Workers
make logs-frontend     # React Frontend

# Restart services
make restart

# Run tests
make test

# Check status
make ps
```

## Detailed Makefile Commands

### Development Workflow

```bash
# First time setup
make setup              # Install all dependencies
cp .env.example .env   # Copy environment template
make dev               # Start all services

# Daily development
make dev               # Start everything
make logs              # Watch logs
make stop              # Stop when done

# Testing
make test              # Run all tests
make test-go           # Go tests only
make test-django       # Django tests only
make test-frontend     # Frontend tests only

# Cleanup
make clean             # Remove containers and volumes
make clean-all         # Nuclear option - remove everything
```

### Service Management

```bash
# Individual service control
make start-api         # Start API Gateway only
make start-orchestrator # Start Django only
make start-worker      # Start Workers only
make start-frontend    # Start Frontend only

make stop-api          # Stop specific service
make stop-orchestrator
make stop-worker
make stop-frontend

make restart-api       # Restart specific service
make restart-orchestrator
make restart-worker
make restart-frontend
```

### Database Operations

```bash
# Django migrations
make migrate           # Run migrations
make makemigrations    # Create new migrations
make shell-db          # PostgreSQL psql shell
make shell-orchestrator # Django shell

# Database reset (⚠️ DESTRUCTIVE)
make db-reset          # Drop and recreate database
```

### Building

```bash
# Build Docker images
make build             # Build all images
make build-api         # Build API Gateway
make build-orchestrator # Build Django
make build-worker      # Build Worker
make build-frontend    # Build Frontend

# Rebuild (no cache)
make rebuild           # Rebuild all from scratch
```

## Health Check Endpoints

### Service Health Status

```bash
# API Gateway
curl http://localhost:8080/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "api-gateway",
#   "timestamp": "2025-01-17T10:00:00Z"
# }

# Django Orchestrator
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "orchestrator",
#   "database": "connected",
#   "redis": "connected"
# }

# Frontend
curl http://localhost:3000

# Should return 200 OK with HTML
```

### Automated Health Check Script

```bash
#!/bin/bash
# health-check.sh

echo "Checking CommandCenter1C services..."

# API Gateway
if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo "✓ API Gateway: healthy"
else
    echo "✗ API Gateway: unhealthy"
fi

# Orchestrator
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo "✓ Orchestrator: healthy"
else
    echo "✗ Orchestrator: unhealthy"
fi

# Frontend
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200"; then
    echo "✓ Frontend: healthy"
else
    echo "✗ Frontend: unhealthy"
fi
```

## Docker Compose Reference

### Service Ports

```
Frontend:           http://localhost:3000
API Gateway:        http://localhost:8080
Django Orchestrator: http://localhost:8000
PostgreSQL:         localhost:5432
Redis:              localhost:6379
```

### Container Names

```
cc1c-frontend
cc1c-api-gateway
cc1c-orchestrator
cc1c-worker
cc1c-postgres
cc1c-redis
cc1c-celery-worker
```

### Docker Compose Commands

```bash
# Start services
docker-compose up -d

# Start with rebuild
docker-compose up -d --build

# Stop services
docker-compose down

# Stop and remove volumes (⚠️ removes data)
docker-compose down -v

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f api-gateway
docker-compose logs -f orchestrator
docker-compose logs -f worker

# Check status
docker-compose ps

# Execute command in container
docker-compose exec orchestrator python manage.py shell
docker-compose exec postgres psql -U postgres
docker-compose exec redis redis-cli

# Scale workers
docker-compose up -d --scale worker=5
```

## Log Analysis

### Log Locations

**Docker logs (через docker-compose):**
```bash
docker-compose logs -f api-gateway
docker-compose logs -f orchestrator
docker-compose logs -f worker
docker-compose logs -f celery-worker
```

**Persistent logs (если настроены volumes):**
```
./logs/api-gateway/
./logs/orchestrator/
./logs/worker/
./logs/celery/
```

### Log Filtering

```bash
# Show only errors
docker-compose logs | grep ERROR

# Show last 100 lines
docker-compose logs --tail=100

# Show logs since specific time
docker-compose logs --since 2025-01-17T10:00:00

# Follow logs for specific service
docker-compose logs -f orchestrator | grep -i "operation"

# Filter by log level
docker-compose logs orchestrator | grep -E "(ERROR|WARNING)"
```

### Common Log Patterns

**API Gateway logs:**
```
INFO: Request started GET /api/operations
INFO: Auth validated for user: admin
INFO: Proxying to orchestrator: http://orchestrator:8000/operations
INFO: Request completed in 125ms
```

**Django Orchestrator logs:**
```
INFO: Operation created: operation_id=123
INFO: Celery task dispatched: task_id=abc-123
INFO: Processing operation for 50 databases
WARNING: Database connection retry (1/3)
ERROR: Failed to process operation: timeout
```

**Worker logs:**
```
INFO: Worker started, pool size: 50
INFO: Processing task: task_id=abc-123
INFO: OData request to base_001: POST Catalog_Users
INFO: Batch completed: 50/50 successful
ERROR: OData request failed: connection timeout
```

## Troubleshooting

### Problem 1: Services Won't Start

**Symptom:**
```bash
make dev
# ERROR: port already in use
```

**Solution:**
```bash
# Check what's using the port
netstat -ano | findstr :8080    # Windows
lsof -i :8080                   # Linux/Mac

# Kill the process or change port in .env
# Then restart
make stop
make dev
```

### Problem 2: Database Connection Errors

**Symptom:**
```
django.db.utils.OperationalError: could not connect to server
```

**Solution:**
```bash
# Check if PostgreSQL container is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres

# Wait for it to be ready
docker-compose exec postgres pg_isready

# Run migrations
make migrate
```

### Problem 3: Redis Connection Issues

**Symptom:**
```
redis.exceptions.ConnectionError: Connection refused
```

**Solution:**
```bash
# Check Redis status
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Restart Redis
docker-compose restart redis
```

### Problem 4: Worker Not Processing Tasks

**Symptom:**
- Operations stuck in "pending" status
- No worker logs

**Solution:**
```bash
# Check if worker is running
docker-compose ps worker

# Check worker logs
docker-compose logs worker

# Check Redis queue
docker-compose exec redis redis-cli
> LLEN operations_queue
> LRANGE operations_queue 0 -1

# Restart worker
docker-compose restart worker
```

### Problem 5: Frontend Not Loading

**Symptom:**
```
Cannot GET /
```

**Solution:**
```bash
# Check if frontend container is running
docker-compose ps frontend

# Check logs
docker-compose logs frontend

# Rebuild frontend
docker-compose up -d --build frontend

# Check if API is accessible
curl http://localhost:8080/health
```

### Problem 6: Out of Disk Space

**Symptom:**
```
ERROR: no space left on device
```

**Solution:**
```bash
# Remove unused Docker resources
docker system prune -a

# Remove volumes (⚠️ removes data)
docker volume prune

# Remove specific old images
docker images
docker rmi <image_id>

# Clean project build artifacts
make clean
```

## Environment Variables

### .env File Structure

```bash
# Application
ENV=development
DEBUG=true

# Ports
FRONTEND_PORT=3000
API_GATEWAY_PORT=8080
ORCHESTRATOR_PORT=8000

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=commandcenter
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# 1C Connection
ONEC_BASE_URL=http://your-1c-server/base/odata/standard.odata
ONEC_USERNAME=admin
ONEC_PASSWORD=password

# Workers
WORKER_POOL_SIZE=50
WORKER_TIMEOUT=30

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

## Performance Monitoring

### Container Resource Usage

```bash
# Real-time stats
docker stats

# Specific container
docker stats cc1c-worker

# Expected resource usage (Phase 1):
# API Gateway:     CPU: 5-10%,   RAM: 50-100MB
# Orchestrator:    CPU: 10-20%,  RAM: 200-300MB
# Worker:          CPU: 20-50%,  RAM: 100-200MB
# Frontend:        CPU: 5-10%,   RAM: 100-200MB
# PostgreSQL:      CPU: 5-15%,   RAM: 200-400MB
# Redis:           CPU: 1-5%,    RAM: 50-100MB
```

### Database Performance

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d commandcenter

# Check active connections
SELECT count(*) FROM pg_stat_activity;

# Slow queries
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

# Database size
SELECT pg_size_pretty(pg_database_size('commandcenter'));

# Table sizes
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::text))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::text) DESC;
```

### Redis Monitoring

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check info
> INFO

# Queue lengths
> LLEN operations_queue
> LLEN results_queue

# Memory usage
> INFO memory

# Connected clients
> CLIENT LIST
```

## Deployment Checklist

### Pre-deployment

- [ ] All tests passing (`make test`)
- [ ] Migrations created and tested (`make migrate`)
- [ ] Environment variables configured (`.env`)
- [ ] Health checks responding
- [ ] Logs show no errors
- [ ] Database backed up

### Post-deployment

- [ ] All services started successfully
- [ ] Health checks passing
- [ ] Can create operations
- [ ] Workers processing tasks
- [ ] Frontend accessible
- [ ] Monitoring enabled

## Common Scenarios

### Scenario 1: Starting Fresh Development Session

```bash
# Pull latest changes
git pull

# Start services
make dev

# Check everything is up
make ps

# Watch logs
make logs
```

### Scenario 2: Testing Changes

```bash
# Make code changes...

# Rebuild affected service
make build-orchestrator

# Restart service
make restart-orchestrator

# Check logs
make logs-orchestrator

# Run tests
make test-django
```

### Scenario 3: Debugging Production Issue

```bash
# Connect to production server (via SSH)
ssh user@production-server

# Check service status
make ps

# Check logs
make logs | grep ERROR

# Check health
curl http://localhost:8080/health

# Check database
make shell-db
```

### Scenario 4: Complete Reset

```bash
# Stop everything
make stop

# Remove all containers and volumes
make clean-all

# Rebuild from scratch
make setup

# Start fresh
make dev

# Run migrations
make migrate

# Load fixtures (if any)
python manage.py loaddata initial_data
```

## References

- Main Makefile: `Makefile` (root directory)
- Docker Compose: `docker-compose.yml`
- Environment template: `.env.example`
- Project documentation: `CLAUDE.md`
- Quick start guide: `docs/START_HERE.md`

## Related Skills

При работе с DevOps используй:
- `cc1c-navigator` - для понимания архитектуры и зависимостей
- `cc1c-test-runner` - для запуска тестов после deployment
- `cc1c-sprint-guide` - для проверки текущей фазы и требований
- `cc1c-service-builder` - при создании новых Dockerfiles

---

**Version:** 1.0
**Last Updated:** 2025-01-17
**Changelog:**
- 1.0 (2025-01-17): Initial release with Makefile commands and troubleshooting guide
