# Local Development Guide

Полное руководство по локальной разработке CommandCenter1C на хост-машине (без Docker для application сервисов).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [First Time Setup](#first-time-setup)
- [Daily Workflow](#daily-workflow)
- [Scripts Reference](#scripts-reference)
- [Environment Configuration](#environment-configuration)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)
- [FAQ](#faq)

---

## Overview

### What's Different from Docker Development?

**Old approach (Docker):**
- Все сервисы запускались в Docker контейнерах
- Управление через `docker-compose up/down`
- Изменения требовали rebuild образов
- Медленные циклы разработки

**New approach (Local + Docker Hybrid):**
- **Infrastructure в Docker:** PostgreSQL, Redis, ClickHouse, ras-grpc-gw
- **Application services локально:** Django, Celery, Go services, Frontend
- **Преимущества:**
  - Быстрый hot reload для Python/Go/React
  - Нативная производительность
  - Легкая отладка (прямой доступ к процессам)
  - Удобное управление через PID файлы

---

## Architecture

```
┌─────────────────────────────────────────┐
│         HOST MACHINE (NATIVE)           │
├─────────────────────────────────────────┤
│                                         │
│  React Frontend (port 5173)             │
│  Go API Gateway (port 8080)             │
│  Go Cluster Service (port 8088)         │
│  Go Worker                              │
│  Django Orchestrator (port 8000)        │
│  Celery Worker                          │
│  Celery Beat                            │
│                                         │
└─────────────┬───────────────────────────┘
              │ localhost
┌─────────────▼───────────────────────────┐
│         DOCKER (INFRASTRUCTURE)         │
├─────────────────────────────────────────┤
│                                         │
│  PostgreSQL (port 5432)                 │
│  Redis (port 6379)                      │
│  ClickHouse (ports 8123, 9000)          │
│  ras-grpc-gw (port 9999)                │
│                                         │
└─────────────────────────────────────────┘
```

### Service Ports

| Service | Port | Protocol | Location |
|---------|------|----------|----------|
| Frontend | 5173 | HTTP | Host |
| API Gateway | 8080 | HTTP | Host |
| Orchestrator | 8000 | HTTP | Host |
| Cluster Service | 8088 | HTTP | Host |
| PostgreSQL | 5432 | TCP | Docker |
| Redis | 6379 | TCP | Docker |
| ClickHouse HTTP | 8123 | HTTP | Docker |
| ClickHouse Native | 9000 | TCP | Docker |
| ras-grpc-gw | 9999 | gRPC | Docker |
| Metrics (optional) | 9090 | HTTP | Host |

---

## Prerequisites

### Required Software

1. **Docker & Docker Compose**
   ```bash
   docker --version  # >= 20.10
   docker-compose --version  # >= 2.0
   ```

2. **Python**
   ```bash
   python --version  # >= 3.11
   pip --version
   ```

3. **Go**
   ```bash
   go version  # >= 1.21
   ```

4. **Node.js & npm**
   ```bash
   node --version  # >= 18
   npm --version  # >= 9
   ```

5. **Git**
   ```bash
   git --version  # >= 2.30
   ```

### System Requirements

- **OS:** Windows 10+ (через GitBash), Linux, macOS
- **RAM:** минимум 8GB (рекомендуется 16GB)
- **Disk:** минимум 10GB свободного места
- **CPU:** 4+ cores

---

## First Time Setup

### Step 1: Clone Repository

```bash
cd /c/1CProject
git clone <repository-url> command-center-1c
cd command-center-1c
```

### Step 2: Create Environment File

```bash
# Скопировать пример
cp .env.local.example .env.local

# Отредактировать под свое окружение
nano .env.local
```

**Важные переменные для изменения:**

```bash
# Django secret (generate new!)
DJANGO_SECRET_KEY=<generate-random-secret>

# Database encryption key (generate with script)
DB_ENCRYPTION_KEY=<generate-with-script>

# JWT secret (generate new!)
JWT_SECRET=<generate-random-secret>

# Database credentials
DB_NAME=commandcenter
DB_USER=commandcenter
DB_PASSWORD=<choose-secure-password>

# Redis password (optional but recommended)
REDIS_PASSWORD=<choose-secure-password>
```

**Generate secrets:**

```bash
# Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Database encryption key
cd orchestrator
python ../scripts/generate_encryption_key.py
cd ..

# JWT secret (any random string)
openssl rand -hex 32
```

### Step 3: Install Python Dependencies

```bash
cd orchestrator

# Create virtual environment
python -m venv venv

# Activate (Windows GitBash)
source venv/Scripts/activate

# Or activate (Linux/Mac)
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Return to project root
cd ..
```

### Step 4: Install Node.js Dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 5: Install Go Dependencies

```bash
# API Gateway
cd go-services/api-gateway
go mod download
cd ../..

# Worker
cd go-services/worker
go mod download
cd ../..

# Cluster Service
cd go-services/cluster-service
go mod download
cd ../..
```

### Step 6: Start All Services

```bash
# Make scripts executable (if not already)
chmod +x scripts/dev/*.sh

# Start everything
./scripts/dev/start-all.sh
```

**Это запустит:**
1. Docker infrastructure (PostgreSQL, Redis)
2. Django migrations
3. Django Orchestrator
4. Celery Worker & Beat
5. Go API Gateway
6. Go Worker
7. Go Cluster Service
8. React Frontend

### Step 7: Verify Setup

```bash
# Check all services
./scripts/dev/health-check.sh

# Or manually
curl http://localhost:8080/health  # API Gateway
curl http://localhost:8000/health  # Orchestrator
curl http://localhost:8088/health  # Cluster Service
curl http://localhost:5173         # Frontend
```

### Step 8: Create Superuser (Django Admin)

```bash
cd orchestrator
source venv/Scripts/activate  # or venv/bin/activate
python manage.py createsuperuser
cd ..
```

**Access Django Admin:**
- URL: http://localhost:8000/admin
- Login with created credentials

---

## Daily Workflow

### Morning: Start Development Environment

```bash
cd /c/1CProject/command-center-1c

# Start all services
./scripts/dev/start-all.sh

# Check everything is running
./scripts/dev/health-check.sh

# Watch logs in separate terminal (optional)
./scripts/dev/logs.sh all
```

### During Development

#### Make Code Changes

1. **Edit code** in your favorite IDE/editor
2. **Restart affected service:**

```bash
# After changing Django code
./scripts/dev/restart.sh orchestrator

# After changing Go API Gateway code
./scripts/dev/restart.sh api-gateway

# After changing Frontend code (usually auto-reloads)
./scripts/dev/restart.sh frontend
```

#### View Logs

```bash
# Watch specific service logs
./scripts/dev/logs.sh orchestrator

# Last 200 lines + follow
./scripts/dev/logs.sh api-gateway 200

# All services
./scripts/dev/logs.sh all
```

#### Check Health

```bash
# Full health check
./scripts/dev/health-check.sh

# Quick manual check
curl http://localhost:8080/health
curl http://localhost:8000/health
```

### Database Changes

```bash
cd orchestrator
source venv/Scripts/activate

# Create migration
python manage.py makemigrations

# Apply migration
python manage.py migrate

# Check migration SQL (optional)
python manage.py sqlmigrate <app> <migration_number>

cd ..
```

### Run Tests

```bash
# Django tests
cd orchestrator
source venv/Scripts/activate
pytest
cd ..

# Go tests
cd go-services/api-gateway
go test ./...
cd ../..

# Frontend tests
cd frontend
npm test
cd ..
```

### Evening: Stop Environment

```bash
# Stop all services
./scripts/dev/stop-all.sh
```

---

## Scripts Reference

### start-all.sh

**Purpose:** Запустить все сервисы локально.

```bash
./scripts/dev/start-all.sh
```

**What it does:**
1. Starts Docker infrastructure
2. Waits for PostgreSQL and Redis to be ready
3. Applies Django migrations
4. Starts all application services in background
5. Saves PIDs to `pids/` directory
6. Redirects logs to `logs/` directory

**Created files:**
- `pids/<service>.pid` - Process ID files
- `logs/<service>.log` - Service log files

### stop-all.sh

**Purpose:** Остановить все сервисы.

```bash
./scripts/dev/stop-all.sh
```

**What it does:**
1. Stops all application services (graceful SIGTERM)
2. Waits 10 seconds for graceful shutdown
3. Force kills if not stopped (SIGKILL)
4. Stops Docker infrastructure
5. Cleans up PID files
6. Checks for orphan processes on ports

### restart.sh

**Purpose:** Перезапустить конкретный сервис.

```bash
./scripts/dev/restart.sh <service-name>
```

**Available services:**
- `orchestrator`
- `celery-worker`
- `celery-beat`
- `api-gateway`
- `worker`
- `cluster-service`
- `frontend`

**Example:**
```bash
./scripts/dev/restart.sh orchestrator
```

### logs.sh

**Purpose:** Просмотр логов сервиса.

```bash
./scripts/dev/logs.sh <service-name> [lines]
```

**Examples:**
```bash
# Tail -f (follow)
./scripts/dev/logs.sh orchestrator

# Last 200 lines + follow
./scripts/dev/logs.sh api-gateway 200

# All services summary
./scripts/dev/logs.sh all
```

### health-check.sh

**Purpose:** Проверка статуса всех сервисов.

```bash
./scripts/dev/health-check.sh
```

**Checks:**
1. Process status (via PID files)
2. HTTP endpoints availability
3. Docker services health
4. JSON response validation
5. Port status

---

## Environment Configuration

### .env.local Structure

```bash
# Django
DJANGO_SECRET_KEY=...
DJANGO_SETTINGS_MODULE=config.settings.development
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database (⚠️ localhost, NOT postgres)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=commandcenter
DB_USER=commandcenter
DB_PASSWORD=password
DB_ENCRYPTION_KEY=...

# Redis (⚠️ localhost, NOT redis)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Go Services
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
ORCHESTRATOR_URL=http://localhost:8000  # ⚠️ localhost

# JWT
JWT_SECRET=...
JWT_EXPIRE_TIME=24h

# Frontend
VITE_API_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws

# Cluster Service
CLUSTER_SERVICE_URL=http://localhost:8088

# RAS gRPC Gateway
GRPC_GATEWAY_ADDR=localhost:9999
RAS_SERVER=host.docker.internal:1545
```

### Key Differences: Docker vs Local

| Variable | Docker Value | Local Value |
|----------|--------------|-------------|
| DB_HOST | `postgres` | `localhost` |
| REDIS_HOST | `redis` | `localhost` |
| ORCHESTRATOR_URL | `http://orchestrator:8000` | `http://localhost:8000` |
| CLUSTER_SERVICE_URL | `http://cluster-service:8088` | `http://localhost:8088` |

---

## Troubleshooting

### Port Already in Use

**Problem:**
```
Error: listen tcp :8080: bind: address already in use
```

**Solution:**

**Windows (GitBash):**
```bash
# Find process on port
netstat -ano | findstr :8080

# Kill process
taskkill /PID <pid> /F
```

**Linux/Mac:**
```bash
# Find process on port
lsof -i :8080

# Kill process
kill -9 <pid>
```

**Or restart everything:**
```bash
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

### Database Connection Error

**Problem:**
```
django.db.utils.OperationalError: could not connect to server: Connection refused
```

**Possible causes:**
1. PostgreSQL not started
2. Wrong `DB_HOST` in `.env.local`
3. PostgreSQL not ready yet

**Solution:**
```bash
# 1. Check PostgreSQL is running
docker-compose -f docker-compose.local.yml ps postgres

# 2. Check logs
docker-compose -f docker-compose.local.yml logs postgres

# 3. Restart PostgreSQL
docker-compose -f docker-compose.local.yml restart postgres

# 4. Wait for ready
docker-compose -f docker-compose.local.yml exec postgres pg_isready

# 5. Check .env.local
cat .env.local | grep DB_HOST
# Should be: DB_HOST=localhost (NOT postgres)

# 6. Restart Orchestrator
./scripts/dev/restart.sh orchestrator
```

### Redis Connection Error

**Problem:**
```
redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379
```

**Solution:**
```bash
# 1. Check Redis is running
docker-compose -f docker-compose.local.yml ps redis

# 2. Test connection
docker-compose -f docker-compose.local.yml exec redis redis-cli ping
# Should return: PONG

# 3. Restart Redis
docker-compose -f docker-compose.local.yml restart redis

# 4. Check .env.local
cat .env.local | grep REDIS_HOST
# Should be: REDIS_HOST=localhost (NOT redis)

# 5. Restart services
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh celery-worker
```

### Service Won't Start

**Problem:**
```
✗ Не удалось запустить Django Orchestrator
```

**Solution:**
```bash
# 1. Check logs
cat logs/orchestrator.log

# 2. Run manually for debugging
cd orchestrator
source venv/Scripts/activate
python manage.py runserver 0.0.0.0:8000

# 3. Check dependencies installed
pip install -r requirements.txt

# 4. Check database connection
python manage.py check --database default

# 5. Check migrations
python manage.py showmigrations

# 6. If migrations not applied
python manage.py migrate
```

### Frontend Compilation Error

**Problem:**
```
Module not found: Can't resolve 'react'
```

**Solution:**
```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# 3. Run manually
npm run dev

# 4. Check logs
cat ../logs/frontend.log
```

### Celery Tasks Not Processing

**Problem:**
- Operations stuck in "pending" status
- No worker activity in logs

**Solution:**
```bash
# 1. Check Celery Worker logs
./scripts/dev/logs.sh celery-worker

# 2. Check Redis queue
docker-compose -f docker-compose.local.yml exec redis redis-cli
> LLEN operations_queue
> LRANGE operations_queue 0 -1
> exit

# 3. Restart Celery Worker
./scripts/dev/restart.sh celery-worker

# 4. Check worker is ready
./scripts/dev/logs.sh celery-worker | grep "ready"
```

### PID Files Lost/Corrupted

**Problem:**
```
⚠️  orchestrator: PID файл не найден
```

**Solution:**
```bash
# 1. Clean up PID files
rm -rf pids/*.pid

# 2. Kill remaining processes by port
netstat -ano | findstr :8080  # Windows
# or
lsof -i :8080  # Linux/Mac

taskkill /PID <pid> /F  # Windows
# or
kill -9 <pid>  # Linux/Mac

# 3. Start fresh
./scripts/dev/start-all.sh
```

---

## Advanced Topics

### Hot Reload for Go Services

Вместо manual restart можно использовать hot reload:

```bash
# Install air
go install github.com/cosmtrek/air@latest

# In service directory
cd go-services/api-gateway
air  # Will auto-restart on code changes
```

### Scale Go Workers

Запустить несколько инстансов Go Worker:

```bash
# Start 5 workers
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

### Debug with VS Code

**Django (Orchestrator):**

`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Django: Debug",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/orchestrator/manage.py",
      "args": ["runserver", "0.0.0.0:8000"],
      "django": true,
      "envFile": "${workspaceFolder}/.env.local"
    }
  ]
}
```

**Go (API Gateway):**

`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Go: Debug API Gateway",
      "type": "go",
      "request": "launch",
      "mode": "auto",
      "program": "${workspaceFolder}/go-services/api-gateway/cmd/main.go",
      "envFile": "${workspaceFolder}/.env.local"
    }
  ]
}
```

### Database Backup & Restore

**Backup:**
```bash
# Full database dump
docker-compose -f docker-compose.local.yml exec postgres \
  pg_dump -U commandcenter commandcenter > backup_$(date +%Y%m%d_%H%M%S).sql

# Or with compression
docker-compose -f docker-compose.local.yml exec postgres \
  pg_dump -U commandcenter commandcenter | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Restore:**
```bash
# From uncompressed dump
docker-compose -f docker-compose.local.yml exec -T postgres \
  psql -U commandcenter commandcenter < backup.sql

# From compressed dump
gunzip -c backup.sql.gz | docker-compose -f docker-compose.local.yml exec -T postgres \
  psql -U commandcenter commandcenter
```

### Complete Environment Reset

⚠️ **DESTRUCTIVE:** Удалит все данные!

```bash
# 1. Stop everything
./scripts/dev/stop-all.sh

# 2. Remove Docker volumes (deletes DB data!)
docker-compose -f docker-compose.local.yml down -v

# 3. Clear logs and PIDs
rm -rf logs/*.log pids/*.pid

# 4. Clear celerybeat schedule
rm -f orchestrator/celerybeat-schedule orchestrator/celerybeat-schedule.db

# 5. Start infrastructure
docker-compose -f docker-compose.local.yml up -d

# 6. Wait for database
sleep 10

# 7. Run migrations
cd orchestrator
source venv/Scripts/activate
python manage.py migrate
python manage.py createsuperuser  # recreate admin
cd ..

# 8. Start all services
./scripts/dev/start-all.sh

# 9. Verify
./scripts/dev/health-check.sh
```

### Performance Monitoring

```bash
# Watch health check every 5 seconds
watch -n 5 ./scripts/dev/health-check.sh

# Monitor process resources (Windows)
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
```

### Run with ClickHouse (Analytics)

```bash
# Start with ClickHouse profile
docker-compose -f docker-compose.local.yml --profile analytics up -d

# Check ClickHouse
curl http://localhost:8123/ping
# Should return: Ok.

# Connect to ClickHouse
docker-compose -f docker-compose.local.yml exec clickhouse clickhouse-client
```

### Run with ras-grpc-gw (1C RAS)

```bash
# Start with RAS profile
docker-compose -f docker-compose.local.yml --profile ras up -d

# Check RAS gateway
docker-compose -f docker-compose.local.yml logs ras-grpc-gw
```

---

## FAQ

### Q: Почему не все в Docker?

**A:** Локальный запуск application сервисов дает:
- Быстрый hot reload без rebuild образов
- Нативную производительность (без overhead виртуализации)
- Легкую отладку (прямой доступ к процессам)
- Удобное управление (PID файлы, simple restart)

Infrastructure сервисы (PostgreSQL, Redis) остаются в Docker потому что:
- Сложно установить и настроить локально
- Требуют специфичные версии и конфигурации
- Изолированы от хост-системы

### Q: Можно ли все равно использовать Docker для всего?

**A:** Да, старый `docker-compose.yml` все еще работает для full Docker setup. Но для разработки рекомендуется hybrid подход.

### Q: Что делать если процесс завис?

**A:**
```bash
# Find and kill by port
netstat -ano | findstr :<port>
taskkill /PID <pid> /F

# Or restart service
./scripts/dev/restart.sh <service>
```

### Q: Как посмотреть что процесс действительно запущен?

**A:**
```bash
# Check PID
cat pids/orchestrator.pid

# Check process exists
ps aux | grep $(cat pids/orchestrator.pid)

# Or use health check
./scripts/dev/health-check.sh
```

### Q: Логи не пишутся в файл?

**A:** Проверить:
1. Директория `logs/` создана
2. Процесс запущен через script (не вручную)
3. Права на запись в `logs/`

### Q: Можно ли запустить только один сервис?

**A:** Да, но нужно сначала запустить infrastructure:

```bash
# Start infrastructure only
docker-compose -f docker-compose.local.yml up -d

# Start specific service manually
cd orchestrator
source venv/Scripts/activate
python manage.py runserver 0.0.0.0:8000
```

### Q: Как изменить порты?

**A:** Отредактировать `.env.local`:
```bash
SERVER_PORT=8888  # API Gateway new port
```

Затем перезапустить:
```bash
./scripts/dev/restart.sh api-gateway
```

### Q: Worker не подключается к Redis?

**A:** Проверить:
1. Redis запущен: `docker-compose -f docker-compose.local.yml ps redis`
2. REDIS_HOST=localhost в .env.local
3. Worker читает .env.local при запуске

---

## See Also

- **Main Documentation:** `CLAUDE.md`
- **DevOps Skill:** `.claude/skills/cc1c-devops/SKILL.md`
- **Scripts README:** `scripts/dev/README.md`
- **Commands:**
  - `/dev-start` - `.claude/commands/dev-start.md`
  - `/check-health` - `.claude/commands/check-health.md`
  - `/restart-service` - `.claude/commands/restart-service.md`

---

**Last Updated:** 2025-11-03
**Version:** 1.0
