## MODIFIED Requirements
### Requirement: Poolops bridge MUST иметь детерминированный runtime-контракт
Система ДОЛЖНА (SHALL) использовать canonical bridge endpoint `POST /api/v2/internal/workflows/execute-pool-runtime-step` для pool runtime шагов, КРОМЕ `pool.publication_odata` после Big-bang cutover.

После Big-bang cutover шаг `pool.publication_odata` ДОЛЖЕН (SHALL) исполняться локально в worker через shared `odata-core`.

Bridge endpoint НЕ ДОЛЖЕН (SHALL NOT) выполнять OData side effects для `pool.publication_odata` после cutover и ДОЛЖЕН (SHALL) возвращать non-retryable конфликт с machine-readable кодом.

#### Scenario: publication_odata после cutover исполняется без bridge side effect
- **GIVEN** Big-bang cutover завершён
- **WHEN** worker исполняет шаг `pool.publication_odata`
- **THEN** OData запросы выполняются через worker `odata-core` без вызова bridge endpoint для side effect
- **AND** доменный lifecycle/projection pool run остаётся совместимым с контрактом

#### Scenario: Вызов bridge для publication_odata после cutover отклоняется fail-closed
- **GIVEN** после cutover отправлен bridge-запрос с `operation_type=pool.publication_odata`
- **WHEN** Orchestrator валидирует запрос
- **THEN** endpoint возвращает non-retryable конфликт с machine-readable кодом
- **AND** side effects публикации не выполняются

## ADDED Requirements
### Requirement: Publication workflow step MUST использовать shared `odata-core` transport в Big-bang режиме
Система ДОЛЖНА (SHALL) выполнять Big-bang перенос `pool.publication_odata` на shared `odata-core` синхронно с переключением `odataops`.

Переход на shared `odata-core` НЕ ДОЛЖЕН (SHALL NOT) менять доменные инварианты pool runtime:
- правила `approval_state/publication_step_state`;
- идемпотентность публикации;
- diagnostics contract публикации;
- retry policy ограничения (`max_attempts_total`, `retry_interval_seconds` caps).

#### Scenario: publication_odata сохраняет доменный контракт после Big-bang cutover
- **GIVEN** workflow run дошёл до шага `publication_odata`
- **WHEN** step исполняется через worker `odata-core`
- **THEN** run lifecycle и pool facade status projection остаются совместимыми с текущим контрактом
- **AND** publication diagnostics сохраняют каноническую структуру
- **AND** side effects публикации остаются идемпотентными

### Requirement: OData compatibility profile MUST оставаться source-of-truth для shared transport
Система ДОЛЖНА (SHALL) применять compatibility constraints из `odata-compatibility-profile` при исполнении `publication_odata` через worker `odata-core`.

#### Scenario: shared transport соблюдает compatibility ограничения
- **GIVEN** целевая ИБ требует конкретный write media-type из compatibility profile
- **WHEN** `publication_odata` исполняется через worker `odata-core`
- **THEN** запросы используют совместимый media-type
- **AND** при несовместимом профиле шаг завершается контролируемой fail-closed ошибкой
