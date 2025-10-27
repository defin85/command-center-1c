# Progress Tracking - Интеграционное тестирование

Руководство по тестированию системы отслеживания прогресса установки расширений.

## Цель

Проверить что события прогресса корректно публикуются в Redis pub/sub канал и могут быть получены Django Orchestrator для real-time обновления UI.

## Подготовка

### 1. Запустить Redis

```bash
# Linux/macOS
redis-server

# Windows (если установлен)
redis-server.exe
```

Проверить доступность:
```bash
redis-cli PING
# Ожидаемый ответ: PONG
```

### 2. Настроить config.yaml

Убедитесь что в `config.yaml` указан правильный Redis host:

```yaml
redis:
  host: "localhost"
  port: 6379
  progress_channel: "installation_progress"
```

### 3. Скомпилировать Installation Service

```bash
cd installation-service
make build
```

## Интеграционный тест

### Шаг 1: Подписаться на канал прогресса

В отдельном терминале запустите:

```bash
redis-cli SUBSCRIBE installation_progress
```

Вывод:
```
Reading messages... (press Ctrl-C to quit)
1) "subscribe"
2) "installation_progress"
3) (integer) 1
```

### Шаг 2: Запустить Installation Service

В другом терминале:

```bash
cd installation-service
make run
```

Ожидаемый вывод:
```
{"level":"info","version":"1.0.0-stage4","message":"Starting Installation Service"}
{"level":"info","message":"Progress publisher connected to Redis"}
{"level":"info","workers":10,"message":"Starting worker pool"}
...
```

### Шаг 3: Отправить тестовую задачу

В третьем терминале отправьте задачу в queue:

```bash
redis-cli LPUSH installation_tasks '{
  "task_id": "test-integration-1",
  "database_id": 999,
  "database_name": "TestDB",
  "connection_string": "/S\"localhost\\TestDB\"",
  "username": "Admin",
  "password": "",
  "extension_path": "C:\\Extensions\\Test.cfe",
  "extension_name": "TestExtension",
  "retry_count": 0,
  "created_at": "2025-10-27T12:00:00Z"
}'
```

### Шаг 4: Проверить события в Redis

В терминале с `redis-cli SUBSCRIBE` вы должны увидеть:

#### Событие 1: task_started

```json
1) "message"
2) "installation_progress"
3) "{
  \"event\":\"task_started\",
  \"task_id\":\"test-integration-1\",
  \"database_id\":999,
  \"database_name\":\"TestDB\",
  \"status\":\"in_progress\",
  \"timestamp\":\"2025-10-27T12:00:01Z\"
}"
```

#### Событие 2: task_failed (ожидается из-за несуществующей базы)

```json
1) "message"
2) "installation_progress"
3) "{
  \"event\":\"task_failed\",
  \"task_id\":\"test-integration-1\",
  \"database_id\":999,
  \"database_name\":\"TestDB\",
  \"status\":\"failed\",
  \"duration_seconds\":3,
  \"error_message\":\"installation failed after 3 attempts: ...\",
  \"timestamp\":\"2025-10-27T12:00:04Z\"
}"
```

### Шаг 5: Проверить логи Installation Service

В терминале с Installation Service вы должны увидеть:

```
{"level":"info","worker_id":0,"task_id":"test-integration-1","message":"Processing task"}
{"level":"debug","event":"task_started","task_id":"test-integration-1","message":"Progress event published"}
{"level":"info","task_id":"test-integration-1","message":"Starting extension installation"}
...
{"level":"error","task_id":"test-integration-1","message":"Task failed"}
{"level":"debug","event":"task_failed","task_id":"test-integration-1","message":"Progress event published"}
```

## Проверка корректности событий

### Обязательные поля task_started:

- ✅ `event` = "task_started"
- ✅ `task_id` - совпадает с отправленным
- ✅ `database_id` - совпадает с отправленным
- ✅ `database_name` - совпадает с отправленным
- ✅ `status` = "in_progress"
- ✅ `timestamp` - RFC3339 формат

### Обязательные поля task_completed/task_failed:

- ✅ `event` = "task_completed" или "task_failed"
- ✅ `task_id` - совпадает
- ✅ `database_id` - совпадает
- ✅ `status` = "success" или "failed"
- ✅ `duration_seconds` - присутствует и > 0
- ✅ `timestamp` - RFC3339 формат
- ✅ `error_message` - присутствует только для failed

## Успешная установка (реальная 1C база)

Для теста успешной установки используйте реальную 1C базу:

```bash
redis-cli LPUSH installation_tasks '{
  "task_id": "real-test-1",
  "database_id": 1,
  "database_name": "RealBase",
  "connection_string": "/S\"server1c\\RealBase\"",
  "username": "ODataUser",
  "password": "YourPassword",
  "extension_path": "C:\\Extensions\\ODataAutoConfig.cfe",
  "extension_name": "ODataAutoConfig",
  "retry_count": 0,
  "created_at": "2025-10-27T12:00:00Z"
}'
```

Ожидаемые события:
1. `task_started` - сразу
2. `task_completed` - через 30-60 секунд (время установки)

## Тестирование с Python (Orchestrator)

Создайте Python скрипт для тестирования:

```python
#!/usr/bin/env python3
"""
test_progress_tracking.py - Integration test for progress tracking
"""

import redis
import json
import time

def test_progress_subscriber():
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    pubsub = r.pubsub()
    pubsub.subscribe('installation_progress')

    print("Subscribed to installation_progress channel")
    print("Waiting for events...")

    # Push test task
    test_task = {
        "task_id": "python-test-1",
        "database_id": 888,
        "database_name": "PythonTestDB",
        "connection_string": "/S\"localhost\\TestDB\"",
        "username": "Admin",
        "password": "",
        "extension_path": "test.cfe",
        "extension_name": "TestExt",
        "retry_count": 0,
        "created_at": "2025-10-27T12:00:00Z"
    }

    r.lpush("installation_tasks", json.dumps(test_task))
    print(f"Pushed task: {test_task['task_id']}")

    # Listen for events
    events_received = []
    timeout = time.time() + 30  # 30 seconds timeout

    for message in pubsub.listen():
        if message['type'] == 'message':
            event = json.loads(message['data'])
            events_received.append(event)

            print(f"\nReceived event:")
            print(f"  Type: {event['event']}")
            print(f"  Task ID: {event['task_id']}")
            print(f"  Status: {event['status']}")
            print(f"  Timestamp: {event['timestamp']}")

            if 'duration_seconds' in event:
                print(f"  Duration: {event['duration_seconds']}s")
            if 'error_message' in event and event['error_message']:
                print(f"  Error: {event['error_message']}")

            # Stop after receiving final event
            if event['event'] in ['task_completed', 'task_failed']:
                break

        if time.time() > timeout:
            print("Timeout waiting for events")
            break

    # Verify events
    print(f"\nTotal events received: {len(events_received)}")

    assert len(events_received) >= 2, "Expected at least 2 events (started + completed/failed)"
    assert events_received[0]['event'] == 'task_started', "First event should be task_started"
    assert events_received[-1]['event'] in ['task_completed', 'task_failed'], \
        "Last event should be task_completed or task_failed"

    print("\n✅ All assertions passed!")

if __name__ == '__main__':
    test_progress_subscriber()
```

Запустить:
```bash
python test_progress_tracking.py
```

## Критерии успеха

### Unit Tests ✅
- [x] Все unit tests проходят (`go test ./internal/progress/`)
- [x] Publisher корректно подключается к Redis
- [x] События корректно сериализуются в JSON
- [x] Context cancellation обрабатывается корректно

### Integration Tests ✅
- [x] События публикуются в Redis pub/sub
- [x] События получаются через `redis-cli SUBSCRIBE`
- [x] Формат JSON корректный и парсится
- [x] Timestamp в RFC3339 формате
- [x] Все обязательные поля присутствуют

### End-to-End (с Orchestrator) ⏳
- [ ] Django Orchestrator получает события
- [ ] База данных обновляется (ExtensionInstallation model)
- [ ] WebSocket отправляет обновления в Frontend
- [ ] UI обновляется в real-time

## Troubleshooting

### События не публикуются

**Проверить:**
1. Redis запущен: `redis-cli PING`
2. Канал правильный: проверьте `config.yaml` → `redis.progress_channel`
3. Логи Installation Service: должны быть `"Progress event published"`

### События получаются, но неверный формат

**Проверить:**
1. Версия Installation Service: должна быть Stage 4+
2. JSON валидный: используйте `jq` для парсинга
3. Сравните с примерами в документации

### Ошибка "context canceled"

**Нормально:** Это ожидаемое поведение при graceful shutdown. Игнорируйте эти ошибки если сервис останавливается корректно.

## Следующие шаги

1. **Django Orchestrator:** Реализовать subscriber для получения событий
2. **WebSocket:** Транслировать события в Frontend
3. **UI:** Обновлять прогресс-бар и таблицу статусов
4. **Monitoring:** Добавить Prometheus метрики для событий

---

**Версия:** 1.0
**Дата:** 2025-10-27
**Stage:** 4 (Progress Tracking) ✅
