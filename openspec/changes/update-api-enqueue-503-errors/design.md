# Design: API v2 enqueue failure → HTTP 503 + unified error codes

## Цели
1) Возвращать `503 Service Unavailable` для ситуаций, когда enqueue в Redis Streams невозможен из-за Redis outage / ошибок XADD.
2) Сделать `error.code` детерминированным и одинаковым для этих кейсов на разных эндпоинтах.
3) Отразить реальное поведение в OpenAPI.

## Термины
- **Redis enqueue failure**: ошибка при записи сообщения в Redis Stream (XADD) или при доступе к DLQ stream.
- **Redis error**: исключение/ошибка, указывающая на недоступность Redis или невозможность выполнить XADD/XRANGE/XREAD и т.п.

## Предлагаемая таксономия error codes (минимум)
- `REDIS_ERROR`: Redis недоступен / XADD не удался / чтение DLQ не удалось из-за Redis.
- `ENQUEUE_FAILED`: enqueue не удался по причинам, которые не классифицированы как Redis outage (fallback).
- `DUPLICATE`: конфликт/дубликат (если применимо; уже используется как `409` в execute-ibcmd-cli).

## Механика определения REDIS_ERROR
Предпочтительный вариант (чтобы не парсить строки ошибок):
- В `OperationsService.enqueue_operation`/`EnqueueResult` иметь машинно-читаемый признак (например `error_code`), который выставляется при исключениях Redis.
- API views принимают решение по `error_code`:
  - `REDIS_ERROR` → `503`
  - `DUPLICATE` → `409`
  - иначе — текущая семантика эндпоинта.

Альтернативы (нежелательно):
- эвристики по тексту исключения (`"ConnectionError"`, `"redis"` и т.п.) — хрупко.

