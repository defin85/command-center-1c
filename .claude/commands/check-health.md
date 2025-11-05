---
description: Check health status of all running services (local processes)
---

Проверить статус здоровья всех локально запущенных сервисов.

## Использование

```bash
# Полная проверка всех сервисов
./scripts/dev/health-check.sh

# Или через команду (если настроен)
make health-check
```

## Что проверяется

### 1. Локальные процессы (по PID файлам)

Проверяет что процессы запущены:

- **orchestrator** - Django Orchestrator (PID из `pids/orchestrator.pid`)
- **celery-worker** - Celery Worker
- **celery-beat** - Celery Beat
- **api-gateway** - Go API Gateway
- **worker** - Go Worker
- **cluster-service** - Go Cluster Service
- **frontend** - React Frontend

**Пример вывода:**
```
[1] Проверка локальных процессов:

  orchestrator: ✓ запущен (PID: 12345)
  celery-worker: ✓ запущен (PID: 12346)
  celery-beat: ✓ запущен (PID: 12347)
  api-gateway: ✓ запущен (PID: 12348)
  worker: ✓ запущен (PID: 12349)
  cluster-service: ✓ запущен (PID: 12350)
  frontend: ✓ запущен (PID: 12351)
```

### 2. HTTP Endpoints

Проверяет доступность HTTP endpoints:

```bash
# Frontend
curl http://localhost:3000

# API Gateway
curl http://localhost:8080/health

# Orchestrator
curl http://localhost:8000/health

# Cluster Service
curl http://localhost:8088/health
```

**Ожидаемые ответы:**

**API Gateway:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": "2h 30m"
}
```

**Orchestrator:**
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected"
}
```

### 3. Docker Services

Проверяет инфраструктурные сервисы:

- **PostgreSQL** - `pg_isready` check
- **Redis** - `redis-cli ping` check
- **ClickHouse** - container status (опционально)
- **ras-grpc-gw** - container status (опционально)

**Пример вывода:**
```
[3] Проверка Docker сервисов:

  PostgreSQL: ✓ запущен и готов
  Redis: ✓ запущен и готов
  ClickHouse: ⚠️  не запущен (опционально)
  ras-grpc-gw: ⚠️  не запущен (опционально)
```

### 4. Проверка соединений (детально)

Проверяет валидность JSON ответов от API:

- API Gateway `/health` возвращает корректный JSON
- Orchestrator `/health` возвращает корректный JSON

### 5. Статус портов

Проверяет что порты открыты и слушают:

- Port 3000 (Frontend)
- Port 8080 (API Gateway)
- Port 8000 (Orchestrator)
- Port 8088 (Cluster Service)
- Port 5432 (PostgreSQL)
- Port 6379 (Redis)

**Пример вывода:**
```
[5] Статус портов:

  Port 3000 (Frontend): ✓ открыт
  Port 8080 (API Gateway): ✓ открыт
  Port 8000 (Orchestrator): ✓ открыт
  Port 8088 (Cluster Service): ✓ открыт
  Port 5432 (PostgreSQL): ✓ открыт
  Port 6379 (Redis): ✓ открыт
```

## Итоговый статус

В конце выводится сводка:

```
========================================
  Итоговый статус
========================================

✓ Все сервисы запущены (7/7)

Управление:
  Запустить все:    ./scripts/dev/start-all.sh
  Остановить все:   ./scripts/dev/stop-all.sh
  Перезапустить:    ./scripts/dev/restart.sh <service>
  Просмотр логов:   ./scripts/dev/logs.sh <service>
```

## Troubleshooting

### Сервис не запущен

**Проблема:**
```
orchestrator: ✗ не запущен (PID файл не найден)
```

**Решение:**
```bash
# Запустить все сервисы
./scripts/dev/start-all.sh

# Или только конкретный сервис
./scripts/dev/restart.sh orchestrator
```

### HTTP endpoint не отвечает

**Проблема:**
```
API Gateway: ✗ не доступен (нет ответа)
```

**Решение:**
```bash
# Проверить логи
./scripts/dev/logs.sh api-gateway

# Проверить что процесс запущен
cat pids/api-gateway.pid
ps aux | grep <pid>

# Перезапустить
./scripts/dev/restart.sh api-gateway
```

### PostgreSQL не готов

**Проблема:**
```
PostgreSQL: ⚠️  запущен, но не готов
```

**Решение:**
```bash
# Проверить статус контейнера
docker-compose -f docker-compose.local.yml ps postgres

# Посмотреть логи
docker-compose -f docker-compose.local.yml logs postgres

# Подождать (может инициализироваться)
sleep 10
./scripts/dev/health-check.sh

# Если не помогло - перезапустить
docker-compose -f docker-compose.local.yml restart postgres
```

### Redis не готов

**Проблема:**
```
Redis: ⚠️  запущен, но не готов
```

**Решение:**
```bash
# Проверить подключение
docker-compose -f docker-compose.local.yml exec redis redis-cli ping

# Должен вернуть: PONG

# Если не отвечает
docker-compose -f docker-compose.local.yml restart redis
```

### Порт закрыт

**Проблема:**
```
Port 8080 (API Gateway): ✗ закрыт
```

**Решение:**
```bash
# Проверить что процесс запущен
ps aux | grep api-gateway

# Проверить что порт не занят другим процессом
netstat -ano | findstr :8080  # Windows
lsof -i :8080                 # Linux/Mac

# Проверить .env.local - возможно указан другой порт
cat .env.local | grep PORT

# Перезапустить сервис
./scripts/dev/restart.sh api-gateway
```

## Integration с мониторингом

Health check можно использовать для автоматического мониторинга:

```bash
# Периодическая проверка (каждые 30 секунд)
watch -n 30 ./scripts/dev/health-check.sh

# Или через cron
*/5 * * * * /path/to/command-center-1c/scripts/dev/health-check.sh >> /var/log/cc1c-health.log 2>&1
```

## Exit Codes

Скрипт возвращает exit code:
- `0` - все сервисы работают нормально
- `1` - есть проблемы с сервисами

Можно использовать в CI/CD или мониторинге:

```bash
if ./scripts/dev/health-check.sh; then
    echo "All services healthy"
else
    echo "Some services are down"
    # Send alert
fi
```

## Быстрая проверка (curl only)

Если нужна только быстрая проверка HTTP endpoints:

```bash
# API Gateway
curl -f http://localhost:8080/health || echo "API Gateway down"

# Orchestrator
curl -f http://localhost:8000/health || echo "Orchestrator down"

# Frontend
curl -f http://localhost:3000 || echo "Frontend down"

# Cluster Service
curl -f http://localhost:8088/health || echo "Cluster Service down"
```

## Проверка конкретного сервиса

Для детальной проверки одного сервиса:

```bash
# 1. Проверить процесс
cat pids/orchestrator.pid
ps aux | grep $(cat pids/orchestrator.pid)

# 2. Проверить endpoint
curl -v http://localhost:8000/health

# 3. Проверить логи
tail -f logs/orchestrator.log

# 4. Проверить соединение с БД (для Django)
cd orchestrator
python manage.py check --database default
```

## Related Commands

- `/dev-start` - запустить все сервисы
- `/run-migrations` - применить миграции

## Related Scripts

- `./scripts/dev/start-all.sh` - запустить все
- `./scripts/dev/stop-all.sh` - остановить все
- `./scripts/dev/restart.sh <service>` - перезапустить сервис
- `./scripts/dev/logs.sh <service>` - просмотр логов
