# Change: Консистентная постановка операций в Redis Streams (Orchestrator enqueue)

## Why
Постановка операций в очередь (`commands:worker:*`) — критичный путь. Сейчас есть риск, что Orchestrator обновляет состояние в Postgres и публикует события, **даже если запись в Redis Streams не произошла**.

Конкретно:
- `RedisClient.enqueue_operation()` глотает исключения и возвращает `False` (`orchestrator/apps/operations/redis_client.py:107-127`),
  а вызывающие сервисы часто **игнорируют результат** (например `orchestrator/apps/operations/services/operations_service/core.py:180-195`).
- В результате возможны “вечные QUEUED”/“pending” в БД без фактической задачи в очереди.

## What Changes
- Ввести единое правило: **если XADD не удался — это ошибка, и состояние в БД НЕ обновляется в QUEUED**.
- Перевести enqueue‑пути на API, которое **пробрасывает исключение** (`enqueue_operation_stream`) или явно проверяет успех и фейлит транзакцию.
- Дофиксить все места enqueue (core/workflow/discovery/health/extra) и привести к одному паттерну.
- Добавить тесты, которые гарантируют: при падении Redis enqueue не происходит “QUEUED в БД”.

## Non-Goals
- Не меняем формат сообщений Message Protocol v2.0.
- Не внедряем полноценный outbox в рамках этого change (это отдельный следующий шаг, если понадобится).
- Не меняем UI и контракты публичного API, кроме поведения ошибок (если это затронуто — будет отдельный change).

## Impact
- Изменения в `orchestrator/apps/operations/services/operations_service/*` и `orchestrator/apps/operations/redis_client.py`.
- Поведение при Redis outage станет fail-closed (ожидаемо для консистентности).

