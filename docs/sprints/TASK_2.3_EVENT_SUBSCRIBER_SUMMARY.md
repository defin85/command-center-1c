# Task 2.3 - Orchestrator Event Subscriber - Summary

**Дата:** 2025-11-12
**Фаза:** Phase 1, Week 2.5-3 (Core Functionality)
**Статус:** ✅ ЗАВЕРШЕНО

---

## Что реализовано

### 1. EventSubscriber Class (`apps/operations/event_subscriber.py`)

**Основные возможности:**
- ✅ Подписка на Redis Streams (НЕ Pub/Sub!)
- ✅ Consumer Groups для at-least-once delivery
- ✅ Автоматическая переподключение при сбоях Redis
- ✅ Graceful shutdown (SIGINT, SIGTERM)
- ✅ Обработка 5 типов событий от Go сервисов
- ✅ Парсинг correlation_id для обновления Task статусов
- ✅ Автоматическое обновление BatchOperation progress

**Подписанные Streams:**
```python
{
    'events:batch-service:extension:installed': '>',
    'events:batch-service:extension:install-failed': '>',
    'events:cluster-service:infobase:locked': '>',
    'events:cluster-service:infobase:unlocked': '>',
    'events:cluster-service:sessions:closed': '>',
}
```

**Consumer Group:** `orchestrator-group`
**Consumer Name:** `orchestrator-{pid}`

### 2. Management Command (`management/commands/run_event_subscriber.py`)

```bash
python manage.py run_event_subscriber [--verbose]
```

**Возможности:**
- ✅ Простой запуск через Django management command
- ✅ Опция `--verbose` для детального логирования
- ✅ Graceful shutdown при Ctrl+C
- ✅ Обработка исключений с понятными сообщениями

### 3. Unit Tests (`tests/test_event_subscriber.py`)

**Coverage: 14 тестов, 100% pass rate**

Тесты покрывают:
- ✅ Инициализация EventSubscriber
- ✅ Создание Consumer Groups
- ✅ Обработка существующих групп (BUSYGROUP)
- ✅ Роутинг событий к обработчикам
- ✅ Парсинг JSON payload
- ✅ Обработка invalid JSON
- ✅ extension:installed → Task.STATUS_COMPLETED
- ✅ extension:install-failed → Task.STATUS_FAILED/RETRY
- ✅ infobase:locked/unlocked events
- ✅ sessions:closed events
- ✅ Парсинг correlation_id
- ✅ Обработка invalid/nonexistent correlation_id
- ✅ Graceful handling Redis connection errors

```bash
$ pytest apps/operations/tests/test_event_subscriber.py -v
============================= 14 passed in 0.82s ==============================
```

### 4. Документация (`README_EVENT_SUBSCRIBER.md`)

Полное руководство включает:
- ✅ Описание архитектуры
- ✅ Формат событий и payload примеры
- ✅ Инструкции по запуску
- ✅ Настройка как systemd service
- ✅ Логирование и мониторинг
- ✅ Troubleshooting guide
- ✅ Best practices

---

## Архитектура

```
Go Services
    │
    ├─ batch-service (Port 8087)
    │    └─ Publish: extension:installed, extension:install-failed
    │
    └─ cluster-service (Port 8088)
         └─ Publish: infobase:locked, infobase:unlocked, sessions:closed
              │
              v
        Redis Streams (localhost:6379)
            events:batch-service:*
            events:cluster-service:*
              │
              │ Consumer Group: orchestrator-group
              v
        EventSubscriber (Python/Django)
            └─ Consumer: orchestrator-{pid}
              │
              v
        Django Models (PostgreSQL)
            ├─ Task.mark_completed(result)
            ├─ Task.mark_failed(error, should_retry=True)
            └─ BatchOperation.update_progress()
```

---

## Ключевые решения

### 1. Correlation ID формат

**Решение:** `batch-<batch_op_id>-<task_id>`

**Пример:** `batch-batch-123-task-456`
- `batch_op_id` = "batch-123"
- `task_id` = "task-456"

**Парсинг:** Ищем последнее вхождение `-task-` для извлечения task_id

```python
# Remove "batch-" prefix
remainder = correlation_id[6:]

# Find last "-task-"
task_prefix_index = remainder.rfind('-task-')
task_id = remainder[task_prefix_index + 1:]  # "task-456"
```

### 2. Redis Streams vs Pub/Sub

**Выбор:** Redis Streams + Consumer Groups

**Преимущества:**
- ✅ At-least-once delivery (Pub/Sub - at-most-once)
- ✅ Message persistence (Pub/Sub - fire-and-forget)
- ✅ Consumer Groups для горизонтального масштабирования
- ✅ ACK mechanism (xack) для надежности
- ✅ Pending messages queue для recovery

### 3. Event Handlers

**Подход:** Route by stream name → dedicated handler

```python
if 'extension:installed' in stream:
    self.handle_extension_installed(payload, correlation_id)
elif 'extension:install-failed' in stream:
    self.handle_extension_failed(payload, correlation_id)
# ...
```

**Альтернативы (не выбраны):**
- ❌ Route by event_type field - требует парсинг всех payload
- ❌ Dynamic handler lookup - сложнее debugging

### 4. Graceful Shutdown

```python
signal.signal(signal.SIGINT, self.shutdown)
signal.signal(signal.SIGTERM, self.shutdown)

def shutdown(self, signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    self.running = False
    sys.exit(0)
```

**Важно:** Set `self.running = False` → main loop exits → safe cleanup

---

## Интеграция с существующими компонентами

### Task Model (`apps/operations/models.py`)

```python
# EventSubscriber использует существующие методы Task:

task.mark_completed(result={'database_id': 'db-123', ...})
# → Устанавливает status=COMPLETED, completed_at, duration_seconds
# → Автоматически вызывает batch_operation.update_progress()

task.mark_failed(
    error_message="Connection timeout",
    error_code="TIMEOUT",
    should_retry=True
)
# → Устанавливает status=RETRY или FAILED
# → Планирует retry с exponential backoff
# → Автоматически вызывает batch_operation.update_progress()
```

**Никаких изменений в Task модель не требуется!**

### BatchOperation Model

**Автоматическое обновление через:**
```python
BatchOperation.update_progress()
# → Подсчитывает completed_tasks, failed_tasks, retry_tasks
# → Вычисляет progress percentage (0-100)
# → Обновляет status (processing → completed/failed)
```

---

## Тестирование

### Запуск тестов

```bash
cd orchestrator
source venv/Scripts/activate
pytest apps/operations/tests/test_event_subscriber.py -v
```

### Результаты

```
14 passed in 0.82s

Coverage:
- EventSubscriber.__init__: ✅
- setup_consumer_groups: ✅
- run_forever: ✅
- process_message: ✅
- handle_extension_installed: ✅
- handle_extension_failed: ✅
- handle_infobase_locked: ✅
- handle_infobase_unlocked: ✅
- handle_sessions_closed: ✅
- _update_task_status_from_correlation_id: ✅
- shutdown: ✅
```

### Тестовые сценарии

1. **Инициализация и setup** ✅
2. **Consumer Groups** ✅
3. **Message routing** ✅
4. **JSON payload parsing** ✅
5. **Task status updates** ✅
6. **Error handling** ✅
7. **Redis connection recovery** ✅

---

## Deployment

### Local Development

```bash
# Terminal 1: Start Redis & PostgreSQL
docker-compose -f docker-compose.local.yml up -d postgres redis

# Terminal 2: Start Django Orchestrator
cd orchestrator
source venv/Scripts/activate
python manage.py runserver

# Terminal 3: Start Event Subscriber
cd orchestrator
source venv/Scripts/activate
python manage.py run_event_subscriber --verbose
```

### Production (systemd)

```bash
# Install service
sudo cp orchestrator/deploy/systemd/event-subscriber.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable event-subscriber
sudo systemctl start event-subscriber

# Check status
sudo systemctl status event-subscriber

# View logs
sudo journalctl -u event-subscriber -f
```

---

## Мониторинг

### Logs

```bash
# В development
tail -f orchestrator/logs/event_subscriber.log

# В production (systemd)
journalctl -u event-subscriber -f

# Искать ошибки
journalctl -u event-subscriber --since "10 minutes ago" | grep ERROR
```

### Redis Streams

```bash
# Проверить длину stream
redis-cli XLEN events:batch-service:extension:installed

# Consumer Group info
redis-cli XINFO GROUPS events:batch-service:extension:installed

# Pending messages
redis-cli XPENDING events:batch-service:extension:installed orchestrator-group
```

### Health Check Script

```bash
#!/bin/bash
# health-check-subscriber.sh

PROCESS=$(ps aux | grep run_event_subscriber | grep -v grep)
if [ -z "$PROCESS" ]; then
    echo "ERROR: Event Subscriber not running"
    exit 1
fi

REDIS_PING=$(redis-cli ping 2>&1)
if [ "$REDIS_PING" != "PONG" ]; then
    echo "ERROR: Redis not responding"
    exit 1
fi

echo "OK: Event Subscriber running, Redis healthy"
exit 0
```

---

## Next Steps (Phase 2.4)

### Интеграционные тесты

- [ ] Тест с реальным Redis instance
- [ ] Тест полного workflow: Go → Redis → Python
- [ ] Performance тест: 1000 events/sec throughput
- [ ] Failure recovery тест: Redis restart, message reprocessing

### Улучшения

- [ ] Prometheus metrics (Phase 3)
  - `event_subscriber_messages_processed_total{stream}`
  - `event_subscriber_errors_total{error_type}`
  - `event_subscriber_processing_duration_seconds{stream}`

- [ ] Dead Letter Queue (DLQ) для failed messages (Phase 4)
  - После N failed attempts → move to DLQ
  - Manual replay mechanism

- [ ] Event replay для recovery (Phase 5)
  - Replay events from timestamp
  - Replay failed events from DLQ

---

## Dependencies

### Python Packages

```txt
redis>=5.0.1  # Redis Streams + Consumer Groups
Django==4.2.25
```

**Уже установлено в requirements.txt** ✅

### External Services

- **Redis 7.0+** - для Streams и Consumer Groups
- **PostgreSQL 15** - для Django models

---

## Acceptance Criteria

- [x] EventSubscriber читает из Redis Streams (НЕ Pub/Sub!)
- [x] Consumer Groups для надежности (at-least-once delivery)
- [x] Handlers для всех событий (installed, failed, locked, etc.)
- [x] Management command для запуска (`run_event_subscriber`)
- [x] Graceful shutdown через signals (SIGINT, SIGTERM)
- [x] Unit tests (14 tests, 100% pass)
- [x] Logging с correlation_id для debugging
- [x] Документация (README_EVENT_SUBSCRIBER.md)

**ВСЕ критерии выполнены!** ✅

---

## Заключение

Task 2.3 успешно завершена. Orchestrator Event Subscriber реализован согласно спецификации EVENT_DRIVEN_ROADMAP.md:

- ✅ Redis Streams integration
- ✅ Consumer Groups для масштабируемости
- ✅ Надежная обработка событий от Go сервисов
- ✅ Автоматическое обновление Task/BatchOperation статусов
- ✅ Comprehensive testing (14 unit tests)
- ✅ Production-ready код с graceful shutdown

**Готово к интеграции с Go сервисами (batch-service, cluster-service)!**

---

## Файлы

```
orchestrator/apps/operations/
├── event_subscriber.py                        # 420 строк
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── run_event_subscriber.py             # 55 строк
├── tests/
│   ├── __init__.py
│   └── test_event_subscriber.py               # 366 строк
└── README_EVENT_SUBSCRIBER.md                 # Полная документация

docs/sprints/
└── TASK_2.3_EVENT_SUBSCRIBER_SUMMARY.md       # Этот файл
```

**Всего:** ~900 строк кода + тесты + документация

---

**Автор:** Claude (AI Assistant)
**Review:** Ready for review
**Merged:** Pending
