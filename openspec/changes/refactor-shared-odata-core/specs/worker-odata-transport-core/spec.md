## ADDED Requirements
### Requirement: Worker OData drivers MUST использовать единый transport core
Система ДОЛЖНА (SHALL) предоставлять единый transport слой `odata-core`, который используется драйверами `odataops` и `poolops`.

`odata-core` ДОЛЖЕН (SHALL) инкапсулировать:
- auth/session management;
- выполнение OData HTTP-запросов;
- retry/backoff policy;
- error normalization;
- batch/upsert/posting helpers.

Драйверы `odataops` и `poolops` НЕ ДОЛЖНЫ (SHALL NOT) дублировать transport-логику вне `odata-core`, кроме domain-specific адаптеров.

#### Scenario: Оба драйвера используют один transport слой
- **GIVEN** worker исполняет `pool.publication_odata` и generic `create`
- **WHEN** формируются OData запросы
- **THEN** оба драйвера используют `odata-core`
- **AND** transport-поведение (auth/session/retry/error mapping) определяется единым кодом

### Requirement: OData retry policy MUST быть детерминированной и ограниченной
Система ДОЛЖНА (SHALL) выполнять повторы только для retryable ошибок:
- transport-level errors;
- HTTP `429`;
- HTTP `5xx`.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять retry для non-retryable `4xx` (кроме `429`).

Система ДОЛЖНА (SHALL) использовать bounded exponential backoff с jitter и ограничением числа попыток.

#### Scenario: Retry выполняется только для retryable ошибки
- **GIVEN** OData запрос завершился ошибкой `503`
- **WHEN** `odata-core` применяет retry policy
- **THEN** выполняется повтор с backoff+jitter в пределах лимита
- **AND** итоговое число попыток не превышает configured maximum

#### Scenario: Retry не выполняется для non-retryable ошибки
- **GIVEN** OData запрос завершился ошибкой `400`
- **WHEN** `odata-core` классифицирует ошибку
- **THEN** повтор не выполняется
- **AND** в драйвер возвращается нормализованная ошибка без дополнительных попыток

### Requirement: OData error normalization MUST быть единым для всех потребителей
Система ДОЛЖНА (SHALL) возвращать из `odata-core` нормализованную модель ошибок с машиночитаемой классификацией, достаточной для:
- `odataops` result mapping;
- `poolops` publication diagnostics;
- telemetry labels.

#### Scenario: Одна и та же OData ошибка классифицируется одинаково в разных драйверах
- **GIVEN** одинаковый ответ OData `409 Conflict`
- **WHEN** ошибку обрабатывают `odataops` и `poolops`
- **THEN** оба пути получают одинаковый normalized error class
- **AND** расхождения в классификации отсутствуют

### Requirement: OData transport observability MUST быть унифицированной
Система ДОЛЖНА (SHALL) публиковать унифицированные telemetry-сигналы для `odata-core`:
- latency;
- retry count;
- финальный status/error class;
- resend attempt для повторных HTTP-запросов.

#### Scenario: Повторные OData вызовы видны в telemetry
- **GIVEN** запрос требует несколько попыток до успеха
- **WHEN** оператор анализирует trace/metrics
- **THEN** видны resend attempts и общее число retry
- **AND** финальный результат коррелируется с тем же operation context

### Requirement: Migration на `odata-core` MUST сохранять внешний контракт драйверов
Система ДОЛЖНА (SHALL) сохранить внешний контракт результатов `odataops` и `poolops` после переключения на `odata-core`.

#### Scenario: Переключение на `odata-core` не меняет публичный результат `odataops`
- **GIVEN** выполняется операция `query` через `odataops`
- **WHEN** драйвер использует `odata-core`
- **THEN** структура `DatabaseResultV2` остаётся совместимой
- **AND** существующие клиенты не требуют изменения контракта
