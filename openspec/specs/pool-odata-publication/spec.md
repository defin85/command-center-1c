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

### Requirement: Publication auth MUST использовать RBAC infobase mapping как source-of-truth
Система ДОЛЖНА (SHALL) резолвить OData username/password для `pool.publication_odata` через `InfobaseUserMapping` на основе publication auth strategy:
- `actor`: mapping по `database + actor_username`;
- `service`: service mapping по `database`.

Система ДОЛЖНА (SHALL) брать OData endpoint (`odata_url`) из `Database`, но НЕ ДОЛЖНА (SHALL NOT) использовать `Database.username/password` как runtime fallback для publication auth после cutover.

#### Scenario: Actor mapping используется для публикации
- **GIVEN** run publication выполняется со стратегией `actor`
- **AND** для target database существует `InfobaseUserMapping` для `actor_username`
- **WHEN** worker исполняет `pool.publication_odata`
- **THEN** credentials запрос использует actor mapping
- **AND** публикация выполняется без обращения к `Database.username/password`

#### Scenario: Отсутствие mapping приводит к fail-closed
- **GIVEN** publication выполняется со стратегией `actor`
- **AND** для части target databases mapping отсутствует
- **WHEN** worker запрашивает credentials
- **THEN** шаг публикации завершается fail-closed с credentials error
- **AND** в diagnostics указываются проблемные target databases без раскрытия секретов

### Requirement: Конфигурация publication auth MUST быть операторски прозрачной
Система ДОЛЖНА (SHALL) разделять operator configuration surfaces для publication:
- `odata_url` задаётся в управлении базой (`Databases`);
- OData user/password задаются в RBAC infobase mappings (`/rbac`, Infobase Users).

Система ДОЛЖНА (SHALL) давать оператору явный сигнал, что legacy database credentials не являются source-of-truth для `pool.publication_odata`.

#### Scenario: Оператор конфигурирует publication через Databases + RBAC
- **GIVEN** у базы заполнен `odata_url`
- **AND** для оператора или service-аккаунта настроен infobase mapping
- **WHEN** запускается pool publication
- **THEN** система использует `odata_url` из базы и credentials из mapping
- **AND** публикация проходит без дополнительного ввода OData пароля в run UI

### Requirement: Publication auth errors MUST быть machine-readable и remediation-friendly
Система ДОЛЖНА (SHALL) возвращать детерминированные machine-readable коды для auth/configuration ошибок publication path:
- `ODATA_MAPPING_NOT_CONFIGURED`;
- `ODATA_MAPPING_AMBIGUOUS`;
- `ODATA_PUBLICATION_AUTH_CONTEXT_INVALID`.

Diagnostics ДОЛЖНЫ (SHALL) содержать `target_database_id` и operator remediation hint (путь в `/rbac`) без раскрытия секретов.

#### Scenario: Ambiguous mapping возвращает детерминированный код и remediation hint
- **GIVEN** для target database обнаружено неоднозначное mapping состояние
- **WHEN** выполняется `pool.publication_odata`
- **THEN** шаг завершается fail-closed с `error_code=ODATA_MAPPING_AMBIGUOUS`
- **AND** diagnostics содержит `target_database_id` и указание на настройку в `/rbac`

### Requirement: Cutover на mapping-only auth MUST проходить через operator-gated rollout
Система ДОЛЖНА (SHALL) перед production cutover выполнять preflight проверки coverage mapping по target databases и staged rehearsal.

Production cutover НЕ ДОЛЖЕН (SHALL NOT) выполняться без documented operator sign-off для staging и prod.

#### Scenario: Preflight coverage fail блокирует production cutover
- **GIVEN** release candidate включает mapping-only auth для `pool.publication_odata`
- **AND** preflight report показывает missing mapping хотя бы для одной target database
- **WHEN** выполняется go/no-go проверка релиза
- **THEN** production cutover отклоняется
- **AND** оператор получает список баз для remediation через `/rbac`

