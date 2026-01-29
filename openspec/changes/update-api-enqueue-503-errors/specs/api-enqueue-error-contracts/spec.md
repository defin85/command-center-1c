## ADDED Requirements

### Requirement: execute-ibcmd-cli возвращает 503 на Redis enqueue failure
Система ДОЛЖНА (SHALL) возвращать `HTTP 503 Service Unavailable`, когда enqueue в Redis Streams не удался из-за Redis outage/ошибки XADD при обработке `POST /api/v2/operations/execute-ibcmd-cli/`. Ответ ДОЛЖЕН (SHALL) содержать `error.code=REDIS_ERROR`.

#### Scenario: Redis недоступен → 503 + REDIS_ERROR
- **GIVEN** Redis недоступен или XADD завершился ошибкой во время enqueue операции
- **WHEN** клиент вызывает `POST /api/v2/operations/execute-ibcmd-cli/`
- **THEN** API возвращает `HTTP 503`
- **AND** тело ответа содержит `error.code = "REDIS_ERROR"`

### Requirement: dlq.retry возвращает 503 на Redis ошибки (read/enqueue)
Система ДОЛЖНА (SHALL) возвращать `HTTP 503 Service Unavailable` при Redis-ошибках (как при чтении DLQ, так и при enqueue) для `POST /api/v2/dlq/retry/`. Ответ ДОЛЖЕН (SHALL) содержать `error.code=REDIS_ERROR`.

#### Scenario: Redis ошибка при чтении DLQ → 503 + REDIS_ERROR
- **GIVEN** Redis возвращает ошибку при чтении DLQ stream
- **WHEN** клиент вызывает `POST /api/v2/dlq/retry/`
- **THEN** API возвращает `HTTP 503`
- **AND** тело ответа содержит `error.code = "REDIS_ERROR"`

### Requirement: OpenAPI документирует 503 для затронутых эндпоинтов
Система ДОЛЖНА (SHALL) отражать `HTTP 503` ответы для затронутых эндпоинтов в `contracts/orchestrator/openapi.yaml`.

#### Scenario: OpenAPI содержит 503 responses
- **GIVEN** OpenAPI контракт orchestrator
- **WHEN** разработчик/клиент проверяет описания эндпоинтов `POST /api/v2/operations/execute-ibcmd-cli/` и `POST /api/v2/dlq/retry/`
- **THEN** оба эндпоинта имеют описание ответа `503`

