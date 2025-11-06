---
description: Check health status of all running services (local processes)
---

Проверить статус всех локально запущенных сервисов.

## Usage

```bash
./scripts/dev/health-check.sh
```

## What It Checks

**3 уровня проверки:**
1. Process check (PID files)
2. HTTP endpoints (/health)
3. Docker services (pg_isready, redis-cli ping)

## Output Example

```
[1] Проверка локальных процессов:
  orchestrator: ✓ запущен (PID: 12345)
  api-gateway: ✓ запущен (PID: 12348)

[2] Проверка HTTP endpoints:
  API Gateway: ✓ доступен (HTTP 200)
  Orchestrator: ✓ доступен (HTTP 200)

[3] Проверка Docker сервисов:
  postgres: ✓ запущен
  redis: ✓ запущен
```

## When to Use

- После запуска всех сервисов (verify)
- При отладке проблем запуска
- Периодически во время разработки
- Перед коммитом изменений

## Common Issues

**Process shows running but HTTP fails:**
```bash
./scripts/dev/logs.sh <service>  # Check logs
```

**All checks fail:**
```bash
./scripts/dev/start-all.sh  # Start all services
```

**PostgreSQL not ready:**
```bash
docker-compose -f docker-compose.local.yml ps postgres
docker-compose -f docker-compose.local.yml logs postgres
docker-compose -f docker-compose.local.yml restart postgres
```

**Redis not ready:**
```bash
docker-compose -f docker-compose.local.yml exec redis redis-cli ping
# Ожидается: PONG
```

Детальный troubleshooting: skill `cc1c-devops`

## Exit Codes

- `0` - все сервисы работают нормально
- `1` - есть проблемы с сервисами

## Periodic Monitoring

```bash
# Автопроверка каждые 30 секунд
watch -n 30 ./scripts/dev/health-check.sh

# В CI/CD pipeline
if ./scripts/dev/health-check.sh; then
    echo "All services healthy"
else
    echo "Some services are down"
fi
```

## Related

- `/dev-start` - запустить все
- `/restart-service` - перезапустить сервис
- Skill: `cc1c-devops`
