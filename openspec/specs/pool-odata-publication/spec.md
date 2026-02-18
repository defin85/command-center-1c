# pool-odata-publication Specification

## Purpose
TBD - created by archiving change add-intercompany-pool-distribution-module. Update Purpose after archive.
## Requirements
### Requirement: Publication MUST использовать OData documents + posting flow
Система ДОЛЖНА (SHALL) публиковать результаты run в ИБ через OData на уровне документов 1С и инициировать проведение документа в 1С после Big-bang cutover через worker-owned `odata-core`.

Система НЕ ДОЛЖНА (SHALL NOT) использовать legacy OData transport path в Orchestrator runtime для `pool.publication_odata` после cutover.

#### Scenario: publication flow исполняется через worker transport-owner
- **WHEN** run переходит в стадию публикации после Big-bang cutover
- **THEN** система выполняет create/update/posting документа через worker `odata-core`
- **AND** legacy Orchestrator publication transport path не используется

### Requirement: Publication MUST поддерживать partial success и управляемые ретраи
Система ДОЛЖНА (SHALL) сохранять доменный контракт `partial_success` и повторной дозаписи failed-частей после переноса transport-owner.

Система ДОЛЖНА (SHALL) сохранять retry policy с `max_attempts=5` и потолком `retry_interval_seconds<=120` как внешний доменный контракт публикации.

#### Scenario: Перенос transport-owner не ломает partial_success контракт
- **GIVEN** публикация в части ИБ завершилась ошибкой после cutover
- **WHEN** запускается retry policy
- **THEN** система выполняет повторные попытки только для failed-целей
- **AND** успешные цели не дублируются
- **AND** итоговый статус run остаётся совместимым (`published`/`partial_success`/`failed`)

### Requirement: External document identity MUST обеспечивать идемпотентный upsert
Система ДОЛЖНА (SHALL) хранить внешний идентификатор документа в целевой ИБ для идемпотентного upsert и прозрачного наблюдения.

Система ДОЛЖНА (SHALL) поддерживать strategy-based resolver идентификатора:
- primary strategy: GUID документа 1С через OData (`_IDRRef` или `Ref_Key`),
- fallback strategy: детерминированный `ExternalRunKey` (`runkey-<sha256[:32]>` от `run_id + target_database_id + document_kind + period`).

#### Scenario: GUID недоступен, применяется fallback стратегия
- **GIVEN** целевая конфигурация/endpoint не возвращает стабильный GUID документа
- **WHEN** выполняется публикация
- **THEN** система использует fallback `ExternalRunKey` и записывает его в поддерживаемое поле документа
- **AND** фиксирует выбранную стратегию в audit trail run

### Requirement: OData diagnostics MUST быть прозрачными для оператора
Система ДОЛЖНА (SHALL) сохранять канонические diagnostics публикации после Big-bang cutover:
- целевую ИБ;
- payload summary;
- HTTP/transport ошибку;
- код доменной ошибки и сообщение;
- номер попытки и время.

#### Scenario: Диагностика публикации совместима до и после cutover
- **GIVEN** run содержит failed-попытки публикации
- **WHEN** оператор открывает diagnostics
- **THEN** структура и обязательные поля diagnostics соответствуют текущему публичному контракту
- **AND** оператор может принять решение о повторной дозаписи без миграции клиентской логики

### Requirement: Publication attempts read-model MUST оставаться каноническим
Система ДОЛЖНА (SHALL) после переноса transport-owner в worker сохранять канонический read-model попыток публикации в `PoolPublicationAttempt` без изменения публичного формата отчёта run.

Система НЕ ДОЛЖНА (SHALL NOT) требовать изменения клиента для чтения `publication_attempts` после cutover.

#### Scenario: Read-model попыток публикации остаётся совместимым после миграции
- **GIVEN** publication path выполняется через worker `odata-core`
- **WHEN** формируется run report
- **THEN** список `publication_attempts` содержит те же обязательные доменные поля попыток
- **AND** клиент продолжает использовать существующий контракт без адаптаций

