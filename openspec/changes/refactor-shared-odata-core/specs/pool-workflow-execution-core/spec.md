## ADDED Requirements
### Requirement: Publication workflow step MUST использовать shared `odata-core` transport
Система ДОЛЖНА (SHALL) исполнять workflow step `publication_odata` через `poolops` с использованием shared transport слоя `odata-core`.

Переход на shared `odata-core` НЕ ДОЛЖЕН (SHALL NOT) менять доменные инварианты pool runtime:
- правила `approval_state/publication_step_state`;
- идемпотентность публикации;
- diagnostics contract публикации;
- retry policy ограничения (`max_attempts_total`, `retry_interval_seconds` caps).

#### Scenario: publication_odata сохраняет доменный контракт после миграции transport-слоя
- **GIVEN** workflow run дошёл до шага `publication_odata`
- **WHEN** step исполняется через `poolops` на shared `odata-core`
- **THEN** run lifecycle и pool facade status projection остаются совместимыми с текущим контрактом
- **AND** publication diagnostics сохраняют каноническую структуру
- **AND** side effects публикации остаются идемпотентными

### Requirement: OData compatibility profile MUST оставаться source-of-truth для shared transport
Система ДОЛЖНА (SHALL) применять compatibility constraints из `odata-compatibility-profile` при исполнении `publication_odata` через shared `odata-core`.

#### Scenario: shared transport соблюдает compatibility ограничения
- **GIVEN** целевая ИБ требует конкретный write media-type из compatibility profile
- **WHEN** `publication_odata` исполняется через shared `odata-core`
- **THEN** запросы используют совместимый media-type
- **AND** при несовместимом профиле шаг завершается контролируемой fail-closed ошибкой
