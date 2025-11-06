---
description: Restart specific service locally
---

Перезапустить конкретный локально запущенный сервис.

## Usage

```bash
./scripts/dev/restart.sh <service-name>
```

## Available Services

- orchestrator, celery-worker, celery-beat (Django)
- api-gateway, worker, cluster-service, batch-service (Go)
- frontend (React)

## Examples

```bash
# После изменений кода
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh api-gateway

# После изменений .env.local
./scripts/dev/restart.sh orchestrator

# При проблемах с сервисом
./scripts/dev/restart.sh cluster-service
```

## What Happens

**Stop phase:**
1. Read PID → SIGTERM (graceful) → wait 10s → SIGKILL
2. Remove PID file

**Start phase:**
1. Clear log → Start in background → Save PID → Verify process

## When to Use

- После изменения кода (hot reload)
- После обновления .env.local
- При зависании или некорректном поведении сервиса
- После обновления зависимостей (pip/npm/go mod)

## Common Issues

**Service won't start:**
```bash
cat logs/<service>.log  # Проверить логи
```

**Port already in use:**
```bash
netstat -ano | findstr :<port>  # Windows
lsof -i :<port>                  # Linux/Mac
taskkill /PID <pid> /F           # Windows
kill -9 <pid>                    # Linux/Mac
```

**Dependencies not installed:**
```bash
# Python
cd orchestrator && pip install -r requirements.txt

# Node.js
cd frontend && npm install
```

Детальный troubleshooting: skill `cc1c-devops` → reference/troubleshooting.md

## Multiple Services Restart

```bash
# Перезапустить все Python сервисы
for service in orchestrator celery-worker celery-beat; do
    ./scripts/dev/restart.sh $service
done

# Или все сразу
./scripts/dev/stop-all.sh && ./scripts/dev/start-all.sh
```

## Monitoring After Restart

```bash
./scripts/dev/restart.sh orchestrator
./scripts/dev/logs.sh orchestrator  # Следить за логами
./scripts/dev/health-check.sh       # Проверить статус
```

## Related

- `/dev-start` - запустить все сервисы
- `/check-health` - проверить статус
- Skill: `cc1c-devops` - полное DevOps управление
