## ADDED Requirements
### Requirement: Worker OData drivers MUST использовать единый transport core
Система ДОЛЖНА (SHALL) предоставлять единый transport слой `odata-core`, который используется:
- драйвером `odataops`;
- execution path шага `pool.publication_odata`.

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

### Requirement: Big-bang migration MUST выполнять атомарный cutover
Система ДОЛЖНА (SHALL) переключать `odataops` и `pool.publication_odata` на `odata-core` в одном релизном окне.

Система НЕ ДОЛЖНА (SHALL NOT) допускать production mixed-mode, в котором только один из путей (`odataops` или `pool.publication_odata`) работает через новый transport core.

#### Scenario: Cutover блокируется при mixed-mode конфигурации
- **GIVEN** release-кандидат включает `odata-core` только для `odataops`
- **WHEN** выполняется release gate проверки Big-bang
- **THEN** cutover не считается валидным
- **AND** релиз отклоняется до синхронного переключения обоих путей

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

### Requirement: Legacy OData transport paths MUST быть отключены в рамках cutover
Система ДОЛЖНА (SHALL) отключить legacy OData transport path для `pool.publication_odata` в Orchestrator runtime в том же релизе, где выполнен Big-bang cutover.

Система НЕ ДОЛЖНА (SHALL NOT) оставлять активными два production transport-path для одного и того же publication side effect после cutover.

#### Scenario: После cutover legacy publication transport недоступен
- **GIVEN** Big-bang cutover завершён успешно
- **WHEN** выполняется `pool.publication_odata`
- **THEN** OData side effect исполняется только через worker `odata-core`
- **AND** legacy Orchestrator transport path не используется

### Requirement: Migration на `odata-core` MUST сохранять внешний контракт драйверов
Система ДОЛЖНА (SHALL) сохранить внешний контракт результатов `odataops` и `poolops` после переключения на `odata-core`.

#### Scenario: Переключение на `odata-core` не меняет публичный результат `odataops`
- **GIVEN** выполняется операция `query` через `odataops`
- **WHEN** драйвер использует `odata-core`
- **THEN** структура `DatabaseResultV2` остаётся совместимой
- **AND** существующие клиенты не требуют изменения контракта
