# Event Subscriber - Redis Streams Integration

## Описание

Event Subscriber - это компонент Django Orchestrator, который подписывается на события из Go сервисов через Redis Streams.

## Архитектура

```
Go Services (worker, cluster-service)
    |
    | Publish events to Redis Streams
    v
Redis Streams (events:*)
    |
    | Consumer Groups (orchestrator-group)
    v
EventSubscriber (Python/Django)
    |
    | Update Django models (Task, BatchOperation)
    v
Django ORM (PostgreSQL)
```

## Поддерживаемые события

### worker

| Stream | Событие | Описание |
|--------|---------|----------|
| `events:worker:completed` | Operation completed | Успешное завершение операции |
| `events:worker:failed` | Operation failed | Ошибка операции |
| `events:worker:cluster-synced` | Cluster synced | Синхронизация кластера завершена |
| `events:worker:clusters-discovered` | Clusters discovered | Обнаружение кластеров завершено |
| `commands:worker:dlq` | Dead Letter Queue | Ошибочные сообщения |

### cluster-service

| Stream | Событие | Описание |
|--------|---------|----------|
| `events:cluster-service:infobase:locked` | Infobase заблокирована | База заблокирована для обслуживания |
| `events:cluster-service:infobase:unlocked` | Infobase разблокирована | Блокировка снята |
| `events:cluster-service:sessions:closed` | Сессии закрыты | Все сессии базы завершены |

## Формат событий

### Go Envelope (в Redis Stream)

```json
{
  "event_type": "worker.completed",
  "correlation_id": "op-123",
  "timestamp": "2025-11-12T10:30:00Z",
  "payload": "{\"operation_id\":\"op-123\",\"summary\":{},\"results\":[]}"
}
```

### Payload примеры

#### worker:completed

```json
{
  "operation_id": "op-123",
  "summary": {},
  "results": []
}
```

## Запуск

### Management Command

```bash
cd orchestrator
source venv/Scripts/activate  # Windows GitBash
python manage.py run_event_subscriber
```

### Опции

```bash
# Verbose logging
python manage.py run_event_subscriber --verbose
```

### Как сервис (systemd)

```ini
[Unit]
Description=CommandCenter1C Event Subscriber
After=redis.target postgresql.target

[Service]
Type=simple
User=commandcenter
WorkingDirectory=/opt/commandcenter1c/orchestrator
Environment="DJANGO_SETTINGS_MODULE=config.settings"
ExecStart=/opt/commandcenter1c/orchestrator/venv/bin/python manage.py run_event_subscriber
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Consumer Groups

Event Subscriber использует Redis Consumer Groups для надежной доставки событий:

- **Consumer Group:** `orchestrator-group`
- **Consumer Name:** `orchestrator-{pid}` (например, `orchestrator-12345`)
- **Гарантии:** At-least-once delivery
- **Масштабирование:** Можно запустить несколько экземпляров (каждый получит свою порцию событий)

## Correlation ID

Формат: `batch-<batch_op_id>-<task_id>`

Примеры:
- `batch-batch-123-task-456` → batch_op_id=`batch-123`, task_id=`task-456`
- `batch-install-789-task-abc-def` → batch_op_id=`install-789`, task_id=`task-abc-def`

Correlation ID используется для связи событий от Go сервисов с Django Task моделью.

## Обработка событий

### extension:installed

1. Парсит `correlation_id` для получения `task_id`
2. Находит `Task` по `task_id`
3. Вызывает `task.mark_completed(result=payload)`
4. Автоматически обновляет `BatchOperation.progress`

### extension:install-failed

1. Парсит `correlation_id`
2. Находит `Task`
3. Вызывает `task.mark_failed(error_message, error_code, should_retry=True)`
4. Планирует retry с exponential backoff (если retry_count < max_retries)

## Логирование

```python
import logging

logger = logging.getLogger('apps.operations.event_subscriber')
```

### Уровни логов

| Уровень | Когда используется |
|---------|-------------------|
| `INFO` | Успешная обработка событий, startup/shutdown |
| `WARNING` | Task не найдена, invalid correlation_id |
| `ERROR` | Ошибки обработки, Redis connection lost |

### Примеры логов

```
INFO EventSubscriber initialized: orchestrator-12345
INFO Created consumer group 'orchestrator-group' for stream 'events:worker:completed'
INFO Processing event: worker.completed (stream=events:worker:completed, correlation_id=op-123)
INFO Extension installed: database=db-123, name=TestExtension, duration=45.20s, correlation_id=batch-batch-123-task-456
INFO Task task-456 marked as completed
WARNING Task not found: task-999 (correlation_id=batch-batch-123-task-999)
ERROR Redis connection lost: ConnectionError, retrying in 5s...
```

## Graceful Shutdown

Event Subscriber обрабатывает сигналы для корректного завершения:

- **SIGINT (Ctrl+C):** Graceful shutdown
- **SIGTERM:** Graceful shutdown

```python
signal.signal(signal.SIGINT, subscriber.shutdown)
signal.signal(signal.SIGTERM, subscriber.shutdown)
```

## Мониторинг

### Health Check

Проверить что subscriber работает:

```bash
# Проверить процесс
ps aux | grep run_event_subscriber

# Проверить Consumer Group в Redis
redis-cli XINFO GROUPS events:worker:completed
```

### Метрики

Prometheus (Django `/metrics`):

- `cc1c_orchestrator_event_subscriber_up{stream,group}` (1/0)
- `cc1c_orchestrator_event_subscriber_consumers{stream,group}`
- `cc1c_orchestrator_event_subscriber_pending{stream,group}`

## Тестирование

### Unit Tests

```bash
cd orchestrator
source venv/Scripts/activate
pytest apps/operations/tests/test_event_subscriber.py -v
```

### Coverage

```bash
pytest apps/operations/tests/test_event_subscriber.py --cov=apps.operations.event_subscriber --cov-report=html
```

### Интеграционные тесты

TODO: Добавить интеграционные тесты с реальным Redis (Phase 2.4)

## Troubleshooting

### Event Subscriber не запускается

```bash
# Проверить Redis доступен
redis-cli ping
# PONG

# Проверить настройки в .env.local
cat .env.local | grep REDIS
# REDIS_HOST=localhost
# REDIS_PORT=6379
```

### Subscriber не получает события

```bash
# Проверить что события публикуются
redis-cli XLEN events:worker:completed
# (integer) 5

# Проверить Consumer Group
redis-cli XINFO GROUPS events:worker:completed
# Должна быть группа "orchestrator-group"

# Проверить pending messages
redis-cli XPENDING events:worker:completed orchestrator-group
```

### Task не обновляется

Проверить логи:

```bash
# WARNING: Task not found
# → Неправильный correlation_id или Task была удалена

# WARNING: Invalid correlation_id format
# → Go сервис отправляет неправильный формат
```

## Best Practices

1. **Запускать один экземпляр** в dev окружении
2. **Масштабировать горизонтально** в production (несколько экземпляров для throughput)
3. **Мониторить pending messages** в Consumer Group
4. **Логировать все correlation_id** для debugging
5. **Использовать systemd** для автоматического перезапуска при сбоях

## Roadmap

- [x] Task 2.3: Basic Event Subscriber (Phase 2, Week 2)
- [ ] Task 2.4: Integration tests с реальным Redis
- [ ] Phase 3: Prometheus metrics
- [ ] Phase 4: Event replay для recovery
- [ ] Phase 5: Dead Letter Queue (DLQ) обработка

## См. также

- [EVENT_DRIVEN_ARCHITECTURE.md](../../../docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md) - Полная архитектура
- [EVENT_DRIVEN_ROADMAP.md](../../../docs/EVENT_DRIVEN_ROADMAP.md) - Детальный план
- [Go Shared Events Library](../../../go-services/shared/events/) - Go реализация
