---
name: cc1c-devops
description: "Execute DevOps tasks for CommandCenter1C: start/stop services locally (host machine), check health endpoints, view logs, run migrations. Use when user needs to start development environment, check service status, debug deployment issues, or mentions local development, health checks, logs, restart."
allowed-tools: ["Bash", "Read"]
---

# cc1c-devops

## Purpose

Управлять DevOps операциями для локальной разработки проекта CommandCenter1C.

**ВАЖНО:** Этот skill предназначен для **локального запуска сервисов на хост-машине**, а НЕ в Docker контейнерах (кроме инфраструктурных сервисов).

## When to Use

Используй этот skill когда:
- Запуск/остановка локального окружения разработки
- Проверка статуса сервисов (PID, HTTP endpoints, порты)
- Просмотр логов локальных процессов
- Перезапуск конкретных сервисов
- Отладка проблем с запуском
- Пользователь упоминает: start, stop, restart, logs, health, status, local development

## Architecture Overview

### Infrastructure (Docker)
Запускаются в Docker контейнерах:
- **PostgreSQL** (port 5432) - primary database
- **Redis** (port 6379) - message queue and cache
- **ClickHouse** (ports 8123, 9000) - analytics (опционально)
- **ras-grpc-gw** (port 9999) - 1C RAS gateway (опционально)

### Application Services (Host Machine)
Запускаются локально на хост-машине:
- **Django Orchestrator** (port 8000) - business logic orchestration
- **Celery Worker** - async task processing
- **Celery Beat** - task scheduler
- **Go API Gateway** (port 8080) - HTTP routing, auth
- **Go Worker** - parallel 1C operations processing
- **Go Cluster Service** (port 8088) - 1C cluster management
- **React Frontend** (port 3000) - UI

## Quick Start Commands

### Essential Commands

```bash
# Запустить все сервисы
./scripts/dev/start-all.sh

# Проверить статус
./scripts/dev/health-check.sh

# Просмотр логов
./scripts/dev/logs.sh <service-name>
./scripts/dev/logs.sh all

# Перезапустить сервис
./scripts/dev/restart.sh <service-name>

# Остановить все
./scripts/dev/stop-all.sh
```

### Available Service Names

- `orchestrator` - Django Orchestrator
- `celery-worker` - Celery Worker
- `celery-beat` - Celery Beat
- `api-gateway` - Go API Gateway
- `worker` - Go Worker
- `cluster-service` - Go Cluster Service
- `frontend` - React Frontend
- `all` - все сервисы (только для logs.sh)

## Detailed Workflows

### First Time Setup

```bash
# 1. Клонировать репозиторий
cd /c/1CProject
git clone <repo-url> command-center-1c
cd command-center-1c

# 2. Создать .env.local файл
cp .env.local.example .env.local

# 3. Отредактировать .env.local под свое окружение
nano .env.local

# 4. Установить Python зависимости
cd orchestrator
python -m venv venv
source venv/bin/activate  # или venv/Scripts/activate на Windows
pip install -r requirements.txt
cd ..

# 5. Установить Node.js зависимости
cd frontend
npm install
cd ..

# 6. Запустить все сервисы
./scripts/dev/start-all.sh

# 7. Проверить что все запустилось
./scripts/dev/health-check.sh
```

### Daily Development Workflow

```bash
# Запустить окружение
./scripts/dev/start-all.sh

# Следить за логами (в отдельном терминале)
./scripts/dev/logs.sh all

# Работать с кодом...

# При изменении кода - перезапустить сервис
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh api-gateway

# Проверить health
./scripts/dev/health-check.sh

# В конце дня - остановить
./scripts/dev/stop-all.sh
```

### Testing Changes

```bash
# 1. Изменить код...

# 2. Перезапустить измененный сервис
./scripts/dev/restart.sh orchestrator

# 3. Проверить логи
./scripts/dev/logs.sh orchestrator

# 4. Проверить health endpoint
curl http://localhost:8000/health

# 5. Запустить тесты
cd orchestrator
pytest
cd ..
```

## Service Management

### Start All Services

```bash
./scripts/dev/start-all.sh
```

**Порядок запуска:**
1. Docker Infrastructure (PostgreSQL, Redis)
2. Django Migrations
3. Django Orchestrator
4. Celery Worker & Beat
5. Go API Gateway
6. Go Worker
7. Go Cluster Service
8. React Frontend

**Что создается:**
- `pids/<service>.pid` - PID файлы для управления процессами
- `logs/<service>.log` - лог файлы сервисов

### Stop All Services

```bash
./scripts/dev/stop-all.sh
```

**Порядок остановки:**
1. Application services (graceful SIGTERM → force SIGKILL)
2. Docker infrastructure (docker-compose down)

**Очистка:**
- Удаляет PID файлы
- Останавливает Docker контейнеры
- Проверяет остаточные процессы на портах

### Restart Specific Service

```bash
./scripts/dev/restart.sh <service-name>
```

**Примеры:**
```bash
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh api-gateway
./scripts/dev/restart.sh frontend
```

**Что происходит:**
1. Читает PID из `pids/<service>.pid`
2. Graceful shutdown (SIGTERM)
3. Ожидает завершения (10 секунд)
4. Force kill если не завершился (SIGKILL)
5. Запускает заново
6. Сохраняет новый PID
7. Проверяет что процесс запустился

## Health Check

### Automated Health Check

```bash
./scripts/dev/health-check.sh
```

**Что проверяется:**

1. **Локальные процессы** (по PID файлам):
   - Проверяет что процессы запущены
   - Показывает PID каждого сервиса

2. **HTTP Endpoints**:
   - Frontend: http://localhost:3000
   - API Gateway: http://localhost:8080/health
   - Orchestrator: http://localhost:8000/health
   - Cluster Service: http://localhost:8088/health

3. **Docker Services**:
   - PostgreSQL: `pg_isready` check
   - Redis: `redis-cli ping` check
   - ClickHouse: container status
   - ras-grpc-gw: container status

4. **Соединения**:
   - Проверка JSON ответов от API
   - Валидация структуры health responses

5. **Порты**:
   - Проверка что порты открыты и слушают
   - Ports: 3000, 8080, 8000, 8088, 5432, 6379

**Пример вывода:**
```
========================================
  CommandCenter1C - Health Check
========================================

[1] Проверка локальных процессов:

  orchestrator: ✓ запущен (PID: 12345)
  celery-worker: ✓ запущен (PID: 12346)
  celery-beat: ✓ запущен (PID: 12347)
  api-gateway: ✓ запущен (PID: 12348)
  worker: ✓ запущен (PID: 12349)
  cluster-service: ✓ запущен (PID: 12350)
  frontend: ✓ запущен (PID: 12351)

[2] Проверка HTTP endpoints:

  Frontend: ✓ доступен (HTTP 200)
  API Gateway: ✓ доступен (HTTP 200)
  Orchestrator: ✓ доступен (HTTP 200)
  Cluster Service: ✓ доступен (HTTP 200)

[3] Проверка Docker сервисов:

  PostgreSQL: ✓ запущен и готов
  Redis: ✓ запущен и готов
  ClickHouse: ⚠️  не запущен (опционально)
  ras-grpc-gw: ⚠️  не запущен (опционально)

========================================
  Итоговый статус
========================================

✓ Все сервисы запущены (7/7)
```

### Manual Health Checks

```bash
# API Gateway
curl http://localhost:8080/health
# Expected: {"status":"healthy","version":"1.0.0","uptime":"2h 30m"}

# Django Orchestrator
curl http://localhost:8000/health
# Expected: {"status":"ok","database":"connected","redis":"connected"}

# Frontend
curl http://localhost:3000
# Expected: HTTP 200 OK

# Cluster Service
curl http://localhost:8088/health
# Expected: {"status":"healthy"}

# PostgreSQL
docker-compose -f docker-compose.local.yml exec postgres pg_isready
# Expected: accepting connections

# Redis
docker-compose -f docker-compose.local.yml exec redis redis-cli ping
# Expected: PONG
```

## Log Management

### View Service Logs

```bash
# Tail logs для конкретного сервиса (follow mode)
./scripts/dev/logs.sh <service-name>

# Указать количество строк
./scripts/dev/logs.sh orchestrator 200

# Все логи (последние 10 строк каждого)
./scripts/dev/logs.sh all
```

**Примеры:**
```bash
# Django Orchestrator
./scripts/dev/logs.sh orchestrator

# API Gateway
./scripts/dev/logs.sh api-gateway

# Frontend
./scripts/dev/logs.sh frontend

# Celery Worker
./scripts/dev/logs.sh celery-worker
```

### Log File Locations

```
logs/
├── orchestrator.log       # Django runserver output
├── celery-worker.log      # Celery worker tasks
├── celery-beat.log        # Celery beat scheduler
├── api-gateway.log        # Go API Gateway
├── worker.log             # Go Worker
├── cluster-service.log    # Go Cluster Service
└── frontend.log           # React dev server (Vite)
```

### Log Analysis

```bash
# Ошибки в логах Orchestrator
grep ERROR logs/orchestrator.log

# Последние 100 строк с ошибками
tail -n 100 logs/orchestrator.log | grep -i error

# Логи за последний час (если есть timestamps)
tail -n 1000 logs/api-gateway.log | grep "$(date +%H:)"

# Логи всех сервисов с фильтром
grep -i "connection refused" logs/*.log

# Следить за логами нескольких сервисов
tail -f logs/orchestrator.log logs/api-gateway.log
```

### Docker Service Logs

```bash
# PostgreSQL
docker-compose -f docker-compose.local.yml logs postgres

# Redis
docker-compose -f docker-compose.local.yml logs redis

# Follow mode
docker-compose -f docker-compose.local.yml logs -f postgres

# Last 100 lines
docker-compose -f docker-compose.local.yml logs --tail=100 redis
```

## Environment Configuration

### .env.local File

**КРИТИЧНО:** Локальная разработка использует `.env.local`, НЕ `.env`!

```bash
# Создать из примера
cp .env.local.example .env.local

# Отредактировать
nano .env.local
```

### Key Differences from Docker Environment

**Docker compose (.env):**
```bash
DB_HOST=postgres           # service name
REDIS_HOST=redis           # service name
ORCHESTRATOR_URL=http://orchestrator:8000
```

**Local development (.env.local):**
```bash
DB_HOST=localhost          # host machine
REDIS_HOST=localhost       # host machine
ORCHESTRATOR_URL=http://localhost:8000
```

### Essential Variables

```bash
# Django
DJANGO_SECRET_KEY=your-secret
DEBUG=True
DB_HOST=localhost
DB_PORT=5432
DB_NAME=commandcenter
DB_USER=commandcenter
DB_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Go Services
SERVER_PORT=8080
ORCHESTRATOR_URL=http://localhost:8000

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Frontend
VITE_API_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

## Troubleshooting

### Problem 1: Services Won't Start

**Symptom:**
```
Error: listen tcp :8080: bind: address already in use
```

**Solution:**
```bash
# Windows (GitBash)
netstat -ano | findstr :8080
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8080
kill -9 <pid>

# Or stop all and restart
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

### Problem 2: Database Connection Errors

**Symptom:**
```
django.db.utils.OperationalError: could not connect to server
```

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose -f docker-compose.local.yml ps postgres

# Check logs
docker-compose -f docker-compose.local.yml logs postgres

# Restart database
docker-compose -f docker-compose.local.yml restart postgres

# Wait for ready
docker-compose -f docker-compose.local.yml exec postgres pg_isready

# Check .env.local
cat .env.local | grep DB_HOST
# Should be: DB_HOST=localhost (NOT postgres)
```

### Problem 3: Redis Connection Issues

**Symptom:**
```
redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379
```

**Solution:**
```bash
# Check Redis status
docker-compose -f docker-compose.local.yml ps redis

# Test connection
docker-compose -f docker-compose.local.yml exec redis redis-cli ping
# Should return: PONG

# Restart Redis
docker-compose -f docker-compose.local.yml restart redis

# Check .env.local
cat .env.local | grep REDIS_HOST
# Should be: REDIS_HOST=localhost (NOT redis)
```

### Problem 4: Process Not Starting

**Symptom:**
```
✗ Не удалось запустить Django Orchestrator
```

**Solution:**
```bash
# 1. Check logs
cat logs/orchestrator.log

# 2. Run manually for debugging
cd orchestrator
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000

# 3. Check dependencies
pip install -r requirements.txt

# 4. Check database connection
python manage.py check --database default

# 5. Check migrations
python manage.py showmigrations
```

### Problem 5: Frontend Not Loading

**Symptom:**
```
Module not found: Can't resolve 'react'
```

**Solution:**
```bash
cd frontend

# Install dependencies
npm install

# Clear cache
rm -rf node_modules package-lock.json
npm install

# Run manually
npm run dev

# Check logs
cat ../logs/frontend.log
```

### Problem 6: PID Files Lost/Corrupted

**Symptom:**
```
⚠️  orchestrator: PID файл не найден
```

**Solution:**
```bash
# Clean up and restart
rm -rf pids/*.pid

# Kill any remaining processes by port
netstat -ano | findstr :8080  # Find PID
taskkill /PID <pid> /F        # Kill it

# Start fresh
./scripts/dev/start-all.sh
```

### Problem 7: Celery Tasks Not Processing

**Symptom:**
- Operations stuck in "pending"
- No worker activity

**Solution:**
```bash
# Check Celery Worker logs
./scripts/dev/logs.sh celery-worker

# Check Redis queue
docker-compose -f docker-compose.local.yml exec redis redis-cli
> LLEN operations_queue
> LRANGE operations_queue 0 -1

# Restart Celery Worker
./scripts/dev/restart.sh celery-worker

# Check worker is connected
./scripts/dev/logs.sh celery-worker | grep "ready"
```

## Advanced Operations

### Debug Specific Service

```bash
# Stop all except infrastructure
./scripts/dev/stop-all.sh

# Start only infrastructure
docker-compose -f docker-compose.local.yml up -d

# Run Django migrations
cd orchestrator
source venv/bin/activate
python manage.py migrate

# Run service manually (foreground, with full output)
python manage.py runserver 0.0.0.0:8000
```

### Scale Workers

```bash
# Start multiple Go Workers
for i in {1..5}; do
    cd go-services/worker
    nohup go run cmd/main.go > ../../logs/worker-$i.log 2>&1 &
    echo $! > ../../pids/worker-$i.pid
    cd ../..
done

# Stop all workers
for pid_file in pids/worker-*.pid; do
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        kill -TERM "$pid" 2>/dev/null || true
        rm -f "$pid_file"
    fi
done
```

### Run with Specific Profiles

```bash
# Start with ClickHouse
docker-compose -f docker-compose.local.yml --profile analytics up -d

# Start with ras-grpc-gw
docker-compose -f docker-compose.local.yml --profile ras up -d

# Start with all profiles
docker-compose -f docker-compose.local.yml --profile analytics --profile ras up -d
```

### Hot Reload Setup (Go services)

```bash
# Install air for Go hot reload
go install github.com/cosmtrek/air@latest

# In go-services/api-gateway
cd go-services/api-gateway
air  # Will auto-restart on code changes

# In go-services/cluster-service
cd go-services/cluster-service
air  # Will auto-restart on code changes
```

### Check Resource Usage

```bash
# Process resource usage (Windows)
for pid_file in pids/*.pid; do
    if [ -f "$pid_file" ]; then
        service=$(basename "$pid_file" .pid)
        pid=$(cat "$pid_file")
        echo "=== $service (PID: $pid) ==="
        tasklist //FI "PID eq $pid" //FO TABLE
    fi
done

# Docker resource usage
docker stats --no-stream

# Disk usage
docker system df
du -sh logs/
```

## Migration Management

```bash
# Create new migration
cd orchestrator
source venv/bin/activate
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migrations status
python manage.py showmigrations

# Rollback migration
python manage.py migrate <app_name> <migration_number>

# Fake migration (mark as applied without running)
python manage.py migrate --fake <app_name> <migration_number>
```

## Common Scenarios

### Scenario 1: Fresh Start After Git Pull

```bash
# Pull latest changes
git pull

# Update dependencies (if changed)
cd orchestrator
source venv/bin/activate
pip install -r requirements.txt
cd ..

cd frontend
npm install
cd ..

# Run migrations (if any)
cd orchestrator
python manage.py migrate
cd ..

# Restart all services
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh

# Check health
./scripts/dev/health-check.sh
```

### Scenario 2: Debugging Production Issue Locally

```bash
# Reproduce issue locally
./scripts/dev/start-all.sh

# Enable debug logging in .env.local
echo "LOG_LEVEL=debug" >> .env.local

# Restart affected service
./scripts/dev/restart.sh orchestrator

# Follow logs
./scripts/dev/logs.sh orchestrator

# Test the issue
curl -X POST http://localhost:8000/api/operations ...

# Check logs for errors
grep ERROR logs/orchestrator.log
```

### Scenario 3: Testing Database Migration

```bash
# Backup database first
docker-compose -f docker-compose.local.yml exec postgres pg_dump -U commandcenter commandcenter > backup.sql

# Create migration
cd orchestrator
python manage.py makemigrations

# Check migration
python manage.py sqlmigrate <app> <migration_number>

# Apply migration
python manage.py migrate

# Test migration
python manage.py shell
>>> from apps.operations.models import Operation
>>> Operation.objects.all()

# If something goes wrong - restore
docker-compose -f docker-compose.local.yml exec -T postgres psql -U commandcenter commandcenter < backup.sql
```

### Scenario 4: Complete Reset

```bash
# Stop everything
./scripts/dev/stop-all.sh

# Remove Docker volumes (⚠️ removes all data)
docker-compose -f docker-compose.local.yml down -v

# Clear logs and PIDs
rm -rf logs/*.log pids/*.pid

# Start infrastructure
docker-compose -f docker-compose.local.yml up -d

# Wait for database
sleep 10

# Run migrations
cd orchestrator
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser  # if needed
cd ..

# Start all services
./scripts/dev/start-all.sh

# Check health
./scripts/dev/health-check.sh
```

## Performance Monitoring

### Monitor Live

```bash
# Watch health check every 5 seconds
watch -n 5 ./scripts/dev/health-check.sh

# Monitor specific port traffic
netstat -ano | findstr :8080  # Windows

# Monitor logs for errors
tail -f logs/*.log | grep -i error
```

### Check Service Metrics

```bash
# API Gateway metrics (if Prometheus enabled)
curl http://localhost:9090/metrics

# Celery inspect
cd orchestrator
source venv/bin/activate
celery -A config inspect active
celery -A config inspect stats
cd ..
```

## Related Skills

При работе с DevOps используй:
- `cc1c-navigator` - для понимания архитектуры и зависимостей
- `cc1c-test-runner` - для запуска тестов после изменений
- `cc1c-sprint-guide` - для проверки текущей фазы разработки

## References

- Main scripts: `scripts/dev/`
- Docker Compose: `docker-compose.local.yml`
- Environment template: `.env.local.example`
- Project docs: `CLAUDE.md`, `docs/START_HERE.md`
- Commands: `.claude/commands/dev-start.md`, `check-health.md`, `restart-service.md`

---

**Version:** 2.0 (Local Development)
**Last Updated:** 2025-11-03
**Changelog:**
- 2.0 (2025-11-03): Complete rewrite for local development (host machine, not Docker)
- 1.0 (2025-01-17): Initial release with Docker Compose workflows
