# Development Scripts - Local Development

Скрипты для управления локальным окружением разработки CommandCenter1C.

## Overview

**ВАЖНО:** Эти скрипты предназначены для **локального запуска сервисов на хост-машине**, а НЕ в Docker контейнерах.

### Architecture

**Infrastructure (Docker):**
- PostgreSQL, Redis, ClickHouse, ras-grpc-gw

**Application Services (Host Machine):**
- Django Orchestrator, Celery Worker/Beat
- Go API Gateway, Worker, Cluster Service
- React Frontend

## Available Scripts

### start-all.sh
Запустить все сервисы локально.

```bash
./scripts/dev/start-all.sh
```

**Что делает:**
1. Запускает Docker infrastructure (PostgreSQL, Redis)
2. Применяет Django миграции
3. Запускает все application сервисы в background
4. Сохраняет PID в `pids/` и логи в `logs/`

### stop-all.sh
Остановить все сервисы.

```bash
./scripts/dev/stop-all.sh
```

**Что делает:**
1. Gracefully останавливает все локальные процессы (SIGTERM)
2. Force kill если не завершились (SIGKILL)
3. Останавливает Docker infrastructure
4. Очищает PID файлы
5. Проверяет остаточные процессы на портах

### restart.sh
Перезапустить конкретный сервис.

```bash
./scripts/dev/restart.sh <service-name>
```

**Available services:**
- `orchestrator` - Django Orchestrator
- `celery-worker` - Celery Worker
- `celery-beat` - Celery Beat
- `api-gateway` - Go API Gateway
- `worker` - Go Worker
- `cluster-service` - Go Cluster Service
- `frontend` - React Frontend

**Примеры:**
```bash
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh api-gateway
./scripts/dev/restart.sh frontend
```

### logs.sh
Просмотр логов сервисов.

```bash
./scripts/dev/logs.sh <service-name> [lines]
```

**Примеры:**
```bash
# Tail -f для конкретного сервиса
./scripts/dev/logs.sh orchestrator

# Последние 200 строк + follow
./scripts/dev/logs.sh api-gateway 200

# Все логи (последние 10 строк каждого)
./scripts/dev/logs.sh all
```

### health-check.sh
Проверка статуса всех сервисов.

```bash
./scripts/dev/health-check.sh
```

**Что проверяется:**
1. Локальные процессы (PID файлы)
2. HTTP endpoints (curl checks)
3. Docker services (PostgreSQL, Redis)
4. JSON responses валидность
5. Порты открыты и слушают

## Quick Start

### First Time Setup

```bash
# 1. Создать .env.local
cp .env.local.example .env.local
nano .env.local

# 2. Установить Python зависимости
cd orchestrator
python -m venv venv
source venv/bin/activate  # или venv/Scripts/activate
pip install -r requirements.txt
cd ..

# 3. Установить Node.js зависимости
cd frontend
npm install
cd ..

# 4. Запустить все
./scripts/dev/start-all.sh

# 5. Проверить статус
./scripts/dev/health-check.sh
```

### Daily Workflow

```bash
# Запустить окружение
./scripts/dev/start-all.sh

# Следить за логами
./scripts/dev/logs.sh all

# При изменении кода - перезапустить сервис
./scripts/dev/restart.sh orchestrator

# Остановить в конце дня
./scripts/dev/stop-all.sh
```

## Directory Structure

После запуска создаются:

```
pids/                    # PID файлы процессов
├── orchestrator.pid
├── celery-worker.pid
├── celery-beat.pid
├── api-gateway.pid
├── worker.pid
├── cluster-service.pid
└── frontend.pid

logs/                    # Логи сервисов
├── orchestrator.log
├── celery-worker.log
├── celery-beat.log
├── api-gateway.log
├── worker.log
├── cluster-service.log
└── frontend.log
```

## Environment Variables

**КРИТИЧНО:** Используйте `.env.local`, НЕ `.env`!

**Ключевые отличия от Docker окружения:**

| Variable | Docker | Local |
|----------|--------|-------|
| DB_HOST | postgres | localhost |
| REDIS_HOST | redis | localhost |
| ORCHESTRATOR_URL | http://orchestrator:8000 | http://localhost:8000 |

## Troubleshooting

### Port Already in Use

```bash
# Windows (GitBash)
netstat -ano | findstr :8080
taskkill /PID <pid> /F

# Or stop all and restart
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

### Database Connection Error

```bash
# Check PostgreSQL
docker-compose -f docker-compose.local.yml ps postgres
docker-compose -f docker-compose.local.yml logs postgres

# Restart
docker-compose -f docker-compose.local.yml restart postgres

# Check .env.local
cat .env.local | grep DB_HOST  # должно быть: localhost
```

### Service Won't Start

```bash
# Check logs
cat logs/orchestrator.log

# Run manually for debugging
cd orchestrator
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

### PID Files Lost

```bash
# Clean up
rm -rf pids/*.pid

# Kill processes by port
netstat -ano | findstr :8080
taskkill /PID <pid> /F

# Start fresh
./scripts/dev/start-all.sh
```

## Advanced Usage

### Run Only Infrastructure

```bash
# Start только Docker services
docker-compose -f docker-compose.local.yml up -d

# Stop infrastructure only
docker-compose -f docker-compose.local.yml down
```

### Debug Specific Service

```bash
# Stop all
./scripts/dev/stop-all.sh

# Start only infrastructure
docker-compose -f docker-compose.local.yml up -d

# Run service manually (foreground)
cd orchestrator
source venv/bin/activate
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
```

### Hot Reload (Go)

```bash
# Install air
go install github.com/cosmtrek/air@latest

# Use air instead of go run
cd go-services/api-gateway
air  # auto-reloads on code changes
```

## Integration with Claude Code

Эти скрипты интегрированы с Claude Code:

**Skills:**
- `cc1c-devops` - DevOps операции

**Commands:**
- `/dev-start` - запустить все
- `/check-health` - проверить статус
- `/restart-service` - перезапустить сервис

## Related Files

- `docker-compose.local.yml` - Docker infrastructure
- `.env.local.example` - environment template
- `CLAUDE.md` - project instructions
- `.claude/skills/cc1c-devops/SKILL.md` - DevOps skill
- `.claude/commands/dev-start.md` - start command
- `.claude/commands/check-health.md` - health check command
- `.claude/commands/restart-service.md` - restart command

## Notes

- Все скрипты используют `set -e` (exit on error)
- Graceful shutdown через SIGTERM (10 sec timeout → SIGKILL)
- Логи пишутся в `logs/` с append режимом
- PID файлы в `pids/` для управления процессами
- Docker services остаются в контейнерах (PostgreSQL, Redis)
- Application services запускаются локально (Django, Go, React)

## Support

При проблемах:
1. Проверить логи: `./scripts/dev/logs.sh <service>`
2. Проверить health: `./scripts/dev/health-check.sh`
3. Проверить `.env.local` конфигурацию
4. Посмотреть `.claude/skills/cc1c-devops/SKILL.md` для детального troubleshooting
