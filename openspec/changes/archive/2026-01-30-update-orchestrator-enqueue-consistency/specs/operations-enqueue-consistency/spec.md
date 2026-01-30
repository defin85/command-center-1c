## ADDED Requirements
### Requirement: Orchestrator не обновляет статус операции в QUEUED без успешного XADD
Система ДОЛЖНА (SHALL) переводить `BatchOperation.status` в `queued` только после успешной записи сообщения в Redis Stream (XADD). Если запись в Redis не удалась, операция НЕ ДОЛЖНА (SHALL NOT) становиться `queued`.

#### Scenario: Redis недоступен → операция не становится queued
- **GIVEN** Redis недоступен или XADD завершился ошибкой
- **WHEN** пользователь (или внутренний код) инициирует enqueue операции
- **THEN** Orchestrator возвращает ошибку enqueue
- **AND** `BatchOperation.status` остаётся не-queued (например `pending`)

