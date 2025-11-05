---
description: Restart specific service locally
---

Перезапустить конкретный локально запущенный сервис.

## Использование

```bash
# Перезапустить сервис
./scripts/dev/restart.sh <service-name>
```

## Доступные сервисы

- **orchestrator** - Django Orchestrator (port 8000)
- **celery-worker** - Celery Worker
- **celery-beat** - Celery Beat scheduler
- **api-gateway** - Go API Gateway (port 8080)
- **worker** - Go Worker (обработка задач)
- **cluster-service** - Go Cluster Service (port 8088)
- **frontend** - React Frontend (port 3000)

## Примеры

```bash
# Перезапустить Django Orchestrator
./scripts/dev/restart.sh orchestrator

# Перезапустить API Gateway
./scripts/dev/restart.sh api-gateway

# Перезапустить Frontend
./scripts/dev/restart.sh frontend

# Перезапустить Celery Worker
./scripts/dev/restart.sh celery-worker
```

## Что происходит

### Шаг 1: Остановка

1. Читает PID из файла `pids/<service>.pid`
2. Отправляет SIGTERM (graceful shutdown)
3. Ожидает завершения процесса (до 10 секунд)
4. Если не завершился - отправляет SIGKILL (force)
5. Удаляет PID файл

### Шаг 2: Запуск

1. Очищает лог файл `logs/<service>.log`
2. Запускает сервис в background
3. Сохраняет новый PID
4. Проверяет что процесс запустился (через 3 секунды)

## Вывод

**Успешный перезапуск:**
```
========================================
  Перезапуск сервиса: orchestrator
========================================

[1/2] Остановка orchestrator...
   Остановка процесса (PID: 12345)...
✓ Процесс остановлен

[2/2] Запуск orchestrator...
✓ orchestrator успешно запущен (PID: 12380)

========================================
  ✓ Сервис перезапущен!
========================================

Лог файл: /c/1CProject/command-center-1c/logs/orchestrator.log
PID файл: /c/1CProject/command-center-1c/pids/orchestrator.pid

Просмотр логов:
  tail -f /c/1CProject/command-center-1c/logs/orchestrator.log
  ./scripts/dev/logs.sh orchestrator
```

**Если процесс не был запущен:**
```
[1/2] Остановка orchestrator...
⚠️  Процесс не запущен

[2/2] Запуск orchestrator...
✓ orchestrator успешно запущен (PID: 12390)
```

## Use Cases

### После изменения кода

```bash
# Изменили код в Django Orchestrator
./scripts/dev/restart.sh orchestrator

# Изменили код в Go API Gateway
./scripts/dev/restart.sh api-gateway

# Изменили код в Frontend
./scripts/dev/restart.sh frontend
```

### После изменения .env.local

```bash
# Изменили переменные окружения
nano .env.local

# Перезапустить все сервисы, которые используют эти переменные
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh api-gateway
./scripts/dev/restart.sh cluster-service
```

### При проблемах с сервисом

```bash
# Сервис завис или ведет себя некорректно
./scripts/dev/restart.sh api-gateway

# Проверить что перезапустился нормально
./scripts/dev/logs.sh api-gateway
```

### После обновления зависимостей

```bash
# Обновили Python зависимости
cd orchestrator
pip install -r requirements.txt

# Перезапустить Django и Celery
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh celery-worker
./scripts/dev/restart.sh celery-beat
```

```bash
# Обновили npm зависимости
cd frontend
npm install

# Перезапустить Frontend
./scripts/dev/restart.sh frontend
```

## Troubleshooting

### Сервис не запускается

**Проблема:**
```
✗ Не удалось запустить orchestrator
```

**Решение:**
```bash
# 1. Посмотреть логи для диагностики
cat logs/orchestrator.log

# 2. Запустить вручную для детального вывода
cd orchestrator
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000

# 3. Проверить .env.local
cat .env.local | grep DB_HOST

# 4. Проверить что БД запущена
docker-compose -f docker-compose.local.yml ps postgres
```

### Процесс не останавливается

**Проблема:**
```
Процесс не завершился gracefully, принудительная остановка...
```

**Причины:**
- Процесс завис
- Обрабатывает длительную операцию
- Не обрабатывает SIGTERM

**Решение:**
- Скрипт автоматически использует SIGKILL
- Если все равно не останавливается - убить вручную:

```bash
# Найти процесс
ps aux | grep orchestrator

# Убить
kill -9 <pid>

# Удалить PID файл
rm pids/orchestrator.pid

# Запустить заново
./scripts/dev/restart.sh orchestrator
```

### Порт занят другим процессом

**Проблема:**
```
Error: listen tcp :8080: bind: address already in use
```

**Решение:**
```bash
# Windows (GitBash)
netstat -ano | findstr :8080
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8080
kill -9 <pid>

# Затем перезапустить
./scripts/dev/restart.sh api-gateway
```

### Зависимости не установлены

**Проблема (Python):**
```
ModuleNotFoundError: No module named 'django'
```

**Решение:**
```bash
cd orchestrator
source venv/bin/activate
pip install -r requirements.txt
```

**Проблема (Node.js):**
```
Module not found: Can't resolve 'react'
```

**Решение:**
```bash
cd frontend
npm install
```

## Перезапуск нескольких сервисов

```bash
# Перезапустить все Python сервисы
for service in orchestrator celery-worker celery-beat; do
    ./scripts/dev/restart.sh $service
done

# Перезапустить все Go сервисы
for service in api-gateway worker cluster-service; do
    ./scripts/dev/restart.sh $service
done

# Перезапустить все сервисы (кроме Docker)
for service in orchestrator celery-worker celery-beat api-gateway worker cluster-service frontend; do
    ./scripts/dev/restart.sh $service
done
```

## Альтернатива: Остановить и запустить все

Если нужно перезапустить ВСЕ сервисы:

```bash
# Остановить все
./scripts/dev/stop-all.sh

# Запустить все
./scripts/dev/start-all.sh

# Это быстрее чем перезапускать по одному
```

## Мониторинг после перезапуска

```bash
# Перезапустить
./scripts/dev/restart.sh orchestrator

# Следить за логами
./scripts/dev/logs.sh orchestrator

# В другом терминале - проверить health
./scripts/dev/health-check.sh
```

## Hot Reload альтернативы

Для некоторых сервисов можно настроить hot reload вместо ручного перезапуска:

### Django (без Docker)
```bash
# runserver уже поддерживает auto-reload
python manage.py runserver --noreload  # отключить auto-reload
```

### Go (с air)
```bash
# Установить air
go install github.com/cosmtrek/air@latest

# В директории go-services/api-gateway
air

# Будет автоматически перезапускаться при изменениях
```

### Frontend (Vite)
```bash
# npm run dev уже поддерживает HMR (Hot Module Replacement)
# Изменения применяются автоматически
```

## Related Commands

- `/dev-start` - запустить все сервисы
- `/check-health` - проверить статус

## Related Scripts

- `./scripts/dev/start-all.sh` - запустить все
- `./scripts/dev/stop-all.sh` - остановить все
- `./scripts/dev/logs.sh <service>` - просмотр логов
- `./scripts/dev/health-check.sh` - проверка здоровья
