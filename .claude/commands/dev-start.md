---
description: Start all services for local development (host machine, not Docker)
---

Запустить все сервисы для локальной разработки (с умной автопересборкой).

## Usage

```bash
./scripts/dev/start-all.sh [OPTIONS]
```

## Options

```bash
--force-rebuild      # Принудительная пересборка всех Go сервисов
--no-rebuild         # Пропустить пересборку
--parallel-build     # Параллельная сборка
--verbose            # Детальный вывод
--help               # Справка
```

## Examples

```bash
# Обычный запуск (умная пересборка)
./scripts/dev/start-all.sh

# Принудительная пересборка всех
./scripts/dev/start-all.sh --force-rebuild

# Быстрый старт без пересборки
./scripts/dev/start-all.sh --no-rebuild
```

## What Happens

**Phase 1:** Smart Go Rebuild (автоопределение изменений)
**Phase 2:** Docker services (postgres, redis)
**Phase 3:** Django migrations
**Phase 4:** Python services (orchestrator, celery)
**Phase 5:** Go services (api-gateway, worker, cluster-service, batch-service)
**Phase 6:** Frontend (React)

**⚠️ Порядок критичен:** ras-grpc-gw ПЕРВЫМ перед cluster-service!

## After Starting

```bash
# Проверить статус
./scripts/dev/health-check.sh

# Просмотр логов
./scripts/dev/logs.sh all
```

## Environment Variables

Команда использует `.env.local` файл (НЕ `.env`!):

```bash
# Первый раз - скопировать пример
cp .env.local.example .env.local

# Ключевые отличия от Docker окружения:
# DB_HOST=localhost (не postgres)
# REDIS_HOST=localhost (не redis)
# ORCHESTRATOR_URL=http://localhost:8000
```

## Common Issues

**Services fail to start:**
```bash
./scripts/dev/logs.sh <service>  # Проверить логи
```

**Port already in use:**
```bash
./scripts/dev/stop-all.sh  # Остановить все
./scripts/dev/start-all.sh  # Запустить заново
```

**Database not ready:**
```bash
docker-compose -f docker-compose.local.yml ps postgres
docker-compose -f docker-compose.local.yml logs postgres
docker-compose -f docker-compose.local.yml restart postgres
```

**Redis connection error:**
```bash
docker-compose -f docker-compose.local.yml exec redis redis-cli ping
# Должен вернуть: PONG
```

Детальный troubleshooting: skill `cc1c-devops`

## Files Created

```
pids/               # PID файлы процессов
├── orchestrator.pid
├── celery-worker.pid
├── api-gateway.pid
└── ...

logs/               # Логи сервисов
├── orchestrator.log
├── celery-worker.log
├── api-gateway.log
└── ...
```

## Related

- `/check-health` - проверить статус
- `/restart-service` - перезапустить один сервис
- Skill: `cc1c-devops`
