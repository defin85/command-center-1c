---
description: Start all services for local development (host machine, not Docker)
---

Запустить все сервисы для локальной разработки на хост-машине.

## Что делает эта команда

1. **Запускает Docker инфраструктуру** (PostgreSQL, Redis, ClickHouse, ras-grpc-gw)
2. **Применяет Django миграции** к базе данных
3. **Запускает все application сервисы локально**:
   - Django Orchestrator (port 8000)
   - Celery Worker
   - Celery Beat
   - Go API Gateway (port 8080)
   - Go Worker
   - Go Cluster Service (port 8088)
   - React Frontend (port 3000)

## Использование

```bash
# Простой старт - все сервисы
./scripts/dev/start-all.sh

# Или через make (если настроен Makefile)
make dev-local
```

## Что происходит

### Шаг 1: Docker Infrastructure
```bash
# Запускает docker-compose.local.yml
docker-compose -f docker-compose.local.yml up -d

# Ожидает готовности:
# - PostgreSQL (pg_isready)
# - Redis (redis-cli ping)
```

### Шаг 2: Django Migrations
```bash
cd orchestrator
python manage.py migrate --noinput
```

### Шаг 3-9: Application Services
Каждый сервис запускается в background с сохранением PID и логов:

```bash
# PID файлы: pids/<service>.pid
# Логи: logs/<service>.log
```

## Проверка после запуска

```bash
# Health check всех сервисов
./scripts/dev/health-check.sh

# Или вручную
curl http://localhost:8080/health  # API Gateway
curl http://localhost:8000/health  # Orchestrator
curl http://localhost:8088/health  # Cluster Service
curl http://localhost:3000         # Frontend
```

## Environment Variables

Команда использует `.env.local` файл (НЕ `.env`!):

```bash
# Первый раз - скопировать пример
cp .env.local.example .env.local

# Отредактировать под свое окружение
nano .env.local
```

**Ключевые отличия от Docker окружения:**
- `DB_HOST=localhost` (не `postgres`)
- `REDIS_HOST=localhost` (не `redis`)
- `ORCHESTRATOR_URL=http://localhost:8000` (не `http://orchestrator:8000`)

## Просмотр логов

```bash
# Все логи (последние строки)
./scripts/dev/logs.sh all

# Конкретный сервис (tail -f)
./scripts/dev/logs.sh orchestrator
./scripts/dev/logs.sh api-gateway
./scripts/dev/logs.sh frontend

# Указать количество строк
./scripts/dev/logs.sh orchestrator 200
```

## Остановка сервисов

```bash
# Остановить все
./scripts/dev/stop-all.sh

# Остановит:
# 1. Все локальные процессы (по PID файлам)
# 2. Docker инфраструктуру (docker-compose down)
```

## Перезапуск конкретного сервиса

```bash
# Перезапустить один сервис
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh api-gateway
./scripts/dev/restart.sh frontend

# Полезно при изменении кода
```

## Troubleshooting

### Порт уже занят

**Проблема:**
```
Error: listen tcp :8080: bind: address already in use
```

**Решение:**
```bash
# Windows (GitBash)
netstat -ano | findstr :8080
taskkill /PID <pid> /F

# Или остановить все и начать заново
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

### База данных не готова

**Проблема:**
```
django.db.utils.OperationalError: could not connect to server
```

**Решение:**
```bash
# Проверить статус PostgreSQL
docker-compose -f docker-compose.local.yml ps postgres

# Посмотреть логи
docker-compose -f docker-compose.local.yml logs postgres

# Перезапустить PostgreSQL
docker-compose -f docker-compose.local.yml restart postgres

# Проверить готовность
docker-compose -f docker-compose.local.yml exec postgres pg_isready
```

### Redis не отвечает

**Проблема:**
```
redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379
```

**Решение:**
```bash
# Проверить Redis
docker-compose -f docker-compose.local.yml exec redis redis-cli ping

# Должен вернуть: PONG

# Если не отвечает - перезапустить
docker-compose -f docker-compose.local.yml restart redis
```

### Сервис не запускается

**Проблема:**
```
✗ Не удалось запустить Django Orchestrator
```

**Решение:**
```bash
# 1. Посмотреть логи
cat logs/orchestrator.log

# 2. Запустить вручную для отладки
cd orchestrator
source venv/bin/activate  # или venv/Scripts/activate
python manage.py runserver 0.0.0.0:8000

# 3. Проверить зависимости
pip install -r requirements.txt
```

### Frontend не компилируется

**Проблема:**
```
Module not found: Can't resolve 'react'
```

**Решение:**
```bash
cd frontend

# Установить зависимости
npm install

# Очистить cache
rm -rf node_modules package-lock.json
npm install

# Запустить вручную
npm run dev
```

## Dependency Order

Сервисы запускаются в правильном порядке зависимостей:

```
1. Docker Infrastructure (PostgreSQL, Redis)
   ↓
2. Django Migrations
   ↓
3. Django Orchestrator ← (зависит от БД)
   ↓
4. Celery Worker ← (зависит от Redis + Orchestrator)
5. Celery Beat ← (зависит от Redis + Orchestrator)
   ↓
6. API Gateway ← (зависит от Orchestrator)
7. Go Worker ← (зависит от Redis)
8. Cluster Service ← (независим)
   ↓
9. Frontend ← (зависит от API Gateway)
```

## Advanced Options

### Запустить только инфраструктуру

```bash
docker-compose -f docker-compose.local.yml up -d
```

### Запустить с ClickHouse (analytics)

```bash
docker-compose -f docker-compose.local.yml --profile analytics up -d
```

### Запустить с ras-grpc-gw

```bash
docker-compose -f docker-compose.local.yml --profile ras up -d
```

### Запустить все профили

```bash
docker-compose -f docker-compose.local.yml --profile analytics --profile ras up -d
```

## Files Created

После запуска создаются директории:

```
pids/               # PID файлы процессов
├── orchestrator.pid
├── celery-worker.pid
├── celery-beat.pid
├── api-gateway.pid
├── worker.pid
├── cluster-service.pid
└── frontend.pid

logs/               # Логи сервисов
├── orchestrator.log
├── celery-worker.log
├── celery-beat.log
├── api-gateway.log
├── worker.log
├── cluster-service.log
└── frontend.log
```

## Related Commands

- `/check-health` - проверить статус всех сервисов
- `/run-migrations` - применить Django миграции
- `/test-all` - запустить все тесты

## Related Scripts

- `./scripts/dev/start-all.sh` - запустить все
- `./scripts/dev/stop-all.sh` - остановить все
- `./scripts/dev/restart.sh <service>` - перезапустить сервис
- `./scripts/dev/logs.sh <service>` - просмотр логов
- `./scripts/dev/health-check.sh` - проверка здоровья
