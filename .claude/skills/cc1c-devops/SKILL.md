---
name: cc1c-devops
description: "Execute DevOps tasks for CommandCenter1C: start/stop services locally (host machine), check health endpoints, view logs, run migrations. Use when user needs to start development environment, check service status, debug deployment issues, or mentions local development, health checks, logs, restart."
allowed-tools: ["Bash", "Read"]
---

# cc1c-devops

## Purpose

Управлять DevOps операциями для локальной разработки проекта CommandCenter1C.

**Hybrid Development Mode:** Infrastructure сервисы (PostgreSQL, Redis) запускаются в Docker, Application сервисы (Django, Go, React) запускаются на хост-машине.

## When to Use

Используй этот skill когда:
- Запуск/остановка локального окружения разработки
- Проверка статуса сервисов (PID, HTTP endpoints, порты)
- Просмотр логов локальных процессов
- Перезапуск конкретных сервисов после изменений кода
- Отладка проблем с запуском
- Пользователь упоминает: start, stop, restart, logs, health, status, local development

## Quick Commands

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

### Available Services

**Application (Host):**
- `orchestrator` - Django Orchestrator (port 8000)
- `celery-worker` - Celery Worker (async tasks)
- `celery-beat` - Celery Beat (scheduler)
- `api-gateway` - Go API Gateway (port 8080)
- `worker` - Go Worker (parallel processing)
- `cluster-service` - Go Cluster Service (port 8088)
- `batch-service` - Go Batch Service (port 8087)
- `frontend` - React Frontend (port 5173)

**Infrastructure (Docker):**
- `postgres` - PostgreSQL (port 5432)
- `redis` - Redis (port 6379)

**External:**
- `ras-grpc-gw` - RAS gRPC Gateway (port 9999) - в ../ras-grpc-gw

## Critical Service Dependencies

**⚠️ ВАЖНО:** Некоторые сервисы имеют зависимости и должны запускаться в порядке:

### Правильный порядок запуска:

1. **Infrastructure** (PostgreSQL, Redis) - Docker контейнеры
2. **ras-grpc-gw** - **КРИТИЧНО запускать ПЕРВЫМ** перед cluster-service
3. **cluster-service** - зависит от ras-grpc-gw (порт 9999)
4. **batch-service** - независим
5. **Остальные сервисы** - Orchestrator, Celery, API Gateway, Workers, Frontend

### Граф зависимостей:

```
Infrastructure (PostgreSQL, Redis)
  ↓
ras-grpc-gw (external, port 9999)
  ↓
cluster-service ───┐
                   │
batch-service ─────┼──→ Orchestrator ──→ API Gateway ──→ Frontend
                   │         ↓
                   └────→ Celery Workers
```

### Проверка зависимостей перед запуском cluster-service:

```bash
# Check ras-grpc-gw is running
curl http://localhost:8081/health
# Expected: {"service":"ras-grpc-gw","status":"healthy",...}

# Check gRPC port is listening
netstat -ano | findstr :9999  # Windows
lsof -i :9999  # Linux/Mac
```

## Key Concepts

### 1. Hybrid Development Mode

- **Infrastructure** (PostgreSQL, Redis) → Docker контейнеры
- **Application** (Django, Go, React) → локальные процессы на хосте
- **Преимущества:** Hot reload, debugging, IDE integration
- **Требования:** .env.local с DB_HOST=localhost (НЕ postgres)

### 2. PID Management

- Все сервисы управляются через PID файлы: `pids/<service>.pid`
- `./scripts/dev/start-all.sh` создает PID файлы
- `./scripts/dev/stop-all.sh` использует PID для graceful shutdown
- `./scripts/dev/restart.sh` читает PID, останавливает, запускает заново

### 3. Health Check Strategy

- **Process check:** проверка PID файлов
- **HTTP check:** curl health endpoints (8080, 8000, 8088, 5173)
- **Database check:** pg_isready, redis-cli ping
- **Port check:** netstat/lsof для проверки listening ports

### 4. Log Management

- Логи в `logs/<service>.log`
- `./scripts/dev/logs.sh <service>` - tail -f для конкретного сервиса
- `./scripts/dev/logs.sh all` - последние 10 строк всех сервисов
- Docker logs: `docker-compose -f docker-compose.local.yml logs <service>`

### 5. Critical Services (batch-service, cluster-service, ras-grpc-gw)

**batch-service:**
- Установка расширений (.cfe) в базы 1С через subprocess
- Требует EXE_1CV8_PATH в переменных окружения
- Port 8087

**cluster-service:**
- Мониторинг кластеров 1С через gRPC
- **ЗАВИСИМОСТЬ:** ras-grpc-gw ДОЛЖЕН быть запущен первым
- Port 8088

**ras-grpc-gw:**
- gRPC gateway для RAS протокола 1С
- **Внешний репозиторий:** ../ras-grpc-gw
- Ports: 9999 (gRPC), 8081 (HTTP health)
- **⚠️ Запускать ПЕРВЫМ!**

Детали см. {baseDir}/reference/services.md

## Common Operations

### Start Dev Session (утро)

```bash
cd /c/1CProject/command-center-1c
./scripts/dev/start-all.sh
./scripts/dev/health-check.sh
```

### After Code Changes

```bash
# Изменил код Django
./scripts/dev/restart.sh orchestrator

# Изменил код Go API Gateway
./scripts/dev/restart.sh api-gateway

# Изменил код React
./scripts/dev/restart.sh frontend
```

### Debugging Service

```bash
# Проверить логи
./scripts/dev/logs.sh orchestrator

# Проверить health endpoint
curl http://localhost:8000/health

# Запустить вручную (foreground, full output)
cd orchestrator
source venv/Scripts/activate
python manage.py runserver 0.0.0.0:8000
```

### End of Day

```bash
./scripts/dev/stop-all.sh
```

## Critical Constraints

1. **Service Dependencies:** ras-grpc-gw → cluster-service (порядок запуска критичен!)
2. **Environment Files:** .env.local с DB_HOST=localhost (НЕ postgres)
3. **PID Management:** НЕ удаляй pids/ вручную, используй ./scripts/dev/stop-all.sh
4. **Port Conflicts:** Перед запуском проверь что порты свободны (8080, 8000, 8088, 5173, 5432, 6379)
5. **Infrastructure First:** Docker containers (PostgreSQL, Redis) ДОЛЖНЫ быть запущены первыми

## Common Problems

### Services Won't Start
**Symptom:** `Error: address already in use`
**Quick Fix:**
```bash
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

### Database Connection Error
**Symptom:** `could not connect to server`
**Quick Fix:**
```bash
# Check .env.local
cat .env.local | grep DB_HOST
# Should be: DB_HOST=localhost

docker-compose -f docker-compose.local.yml restart postgres
./scripts/dev/restart.sh orchestrator
```

### cluster-service Connection Refused (port 9999)
**Symptom:** `connection refused on port 9999`
**Quick Fix:**
```bash
# Start ras-grpc-gw FIRST
cd ../ras-grpc-gw
go run cmd/main.go localhost:1545

# Wait 3-5 seconds, then start cluster-service
cd /c/1CProject/command-center-1c
./scripts/dev/restart.sh cluster-service
```

### batch-service "1cv8.exe not found"
**Symptom:** `executable file not found`
**Quick Fix:**
```bash
# Set path in .env.local
echo 'EXE_1CV8_PATH=C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe' >> .env.local
./scripts/dev/restart.sh batch-service
```

**Полный troubleshooting:** см. {baseDir}/reference/troubleshooting.md

## References

### Detailed Documentation
- {baseDir}/reference/services.md - детали всех сервисов, API endpoints, env vars
- {baseDir}/reference/troubleshooting.md - решения 13 типичных проблем
- {baseDir}/reference/advanced-ops.md - debug, scaling, profiling, testing

### Related Skills
- `cc1c-navigator` - понимание архитектуры и зависимостей
- `cc1c-test-runner` - запуск тестов после изменений
- `cc1c-sprint-guide` - текущая фаза разработки

### Slash Commands
- `/dev-start` - запустить все сервисы
- `/check-health` - проверить статус
- `/restart-service <name>` - перезапустить сервис
- `/run-migrations` - применить миграции Django

### Project Documentation
- [CLAUDE.md](../../../CLAUDE.md) - главный контекст проекта
- [LOCAL_DEVELOPMENT_GUIDE.md](../../../docs/LOCAL_DEVELOPMENT_GUIDE.md) - полное руководство
- [1C_ADMINISTRATION_GUIDE.md](../../../docs/1C_ADMINISTRATION_GUIDE.md) - RAS/gRPC setup

---

**Version:** 3.0 (Optimized)
**Last Updated:** 2025-11-06
**Changelog:**
- 3.0 (2025-11-06): Refactored to 220 lines, moved details to reference/ files
- 2.1 (2025-11-05): Add batch-service, ras-grpc-gw details, service dependencies
- 2.0 (2025-11-03): Complete rewrite for local development (host machine)
