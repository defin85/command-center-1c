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

### Requirement: Publication transport MUST поддерживать chain payload с per-document entity
Система ДОЛЖНА (SHALL) принимать publication payload, где для каждой target database передаётся ordered chain документов с per-document `entity_name`, payload данными и link metadata.

Система ДОЛЖНА (SHALL) сохранять backward compatibility для legacy single-entity payload на переходном этапе.

#### Scenario: Worker публикует chain документов разных entity в одной target database
- **GIVEN** publication payload содержит ordered chain из документов разных `entity_name`
- **WHEN** worker исполняет `pool.publication_odata`
- **THEN** документы создаются/проводятся в порядке chain
- **AND** результат публикации содержит попытки и статусы по документам цепочки

### Requirement: Publication MUST обеспечивать обязательную связанную счёт-фактуру по policy
Система ДОЛЖНА (SHALL) при `invoice_mode=required` публиковать связанную счёт-фактуру как часть той же цепочки и проверять корректность linkage с базовым документом.

Система НЕ ДОЛЖНА (SHALL NOT) завершать публикацию success для цепочки, где required invoice не создана или не связана корректно.

#### Scenario: Required счёт-фактура публикуется и связывается с базовым документом
- **GIVEN** chain содержит базовый документ и шаг required invoice
- **WHEN** worker выполняет публикацию цепочки
- **THEN** сначала создаётся базовый документ, затем связанная счёт-фактура
- **AND** linkage между документами фиксируется в publication diagnostics/read-model

### Requirement: Chain-aware retry MUST сохранять partial success semantics
Система ДОЛЖНА (SHALL) при retry publication повторять только failed документы/цепочки для failed targets и не дублировать успешные side effects.

Система ДОЛЖНА (SHALL) сохранять внешний контракт статусов run (`published|partial_success|failed`) и лимиты retry policy.

#### Scenario: Retry повторяет только failed часть chain-публикации
- **GIVEN** в target database базовый документ успешно опубликован, а связанная счёт-фактура завершилась ошибкой
- **WHEN** оператор запускает retry failed
- **THEN** worker повторяет только failed шаг(и) цепочки
- **AND** already-successful шаги не дублируются

### Requirement: Publication payload MUST использовать resolved master-data refs из binding artifact
Система ДОЛЖНА (SHALL) при `pool.publication_odata` формировать документный payload на основе `master_data_binding_artifact` и передавать в OData только resolved ссылки на сущности ИБ (`Ref_Key`/эквивалент), а не свободные строковые значения.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять implicit free-text lookup мастер-данных в момент OData side effects, если required binding отсутствует.

#### Scenario: Публикация использует resolved refs для номенклатуры и контрагента
- **GIVEN** `master_data_binding_artifact` содержит resolved ссылки для `Item` и `Party` в target ИБ
- **WHEN** worker исполняет `pool.publication_odata`
- **THEN** в OData payload используются соответствующие resolved refs
- **AND** публикация не опирается на lookup по текстовым наименованиям

#### Scenario: Отсутствие required binding блокирует OData side effects
- **GIVEN** для required сущности в target ИБ отсутствует resolved binding в artifact
- **WHEN** worker подготавливает payload публикации
- **THEN** шаг завершается fail-closed до OData create/post
- **AND** diagnostics содержит machine-readable код `MASTER_DATA_BINDING_CONFLICT` или `MASTER_DATA_ENTITY_NOT_FOUND`

### Requirement: OData verification MUST поддерживать UTF-8 Basic auth для document-by-ref проверки
Система верификации публикации MUST получать документы из OData по published refs с использованием UTF-8 кодирования credentials в Basic Authorization header.

#### Scenario: Кириллические учетные данные не ломают verification transport
- **GIVEN** target infobase использует логин/пароль с non-latin символами
- **WHEN** verifier выполняет запрос `$metadata` и чтение опубликованных документов
- **THEN** transport использует UTF-8 Basic Authorization
- **AND** проверка не падает из-за `latin-1` кодирования

### Requirement: OData verification MUST проверять полноту опубликованных документов по completeness profile
Verifier MUST сравнивать фактически опубликованные документы с completeness profile: обязательные реквизиты и обязательные табличные части с минимальным числом строк.

#### Scenario: Отсутствующая табличная часть фиксируется как mismatch
- **GIVEN** published ref указывает на документ без обязательной строки табличной части
- **WHEN** verifier выполняет проверку по profile
- **THEN** формируется machine-readable mismatch с указанием `entity_name`, `field_or_table_path` и `database_id`
- **AND** run verification status устанавливается в failed

### Requirement: Publication payload MUST использовать resolved GLAccount refs из binding artifact
Система ДОЛЖНА (SHALL) при `pool.publication_odata` формировать account fields документа через reusable-data binding artifact и передавать в OData только target-local resolved refs (`Ref_Key` или эквивалент), а не свободные string literals.

Система НЕ ДОЛЖНА (SHALL NOT) использовать cross-infobase `Ref_Key` reuse или implicit lookup по account code в момент OData side effects.

#### Scenario: Account field публикации использует resolved target-local ref
- **GIVEN** `document_policy` использует canonical `GLAccount` token
- **AND** target ИБ имеет валидный `GLAccount` binding
- **WHEN** worker подготавливает publication payload
- **THEN** account field получает resolved target-local ref из binding artifact
- **AND** payload не содержит свободный account code вместо OData reference

#### Scenario: Отсутствие required account binding блокирует OData side effects
- **GIVEN** policy требует canonical `GLAccount`, но для target ИБ binding отсутствует
- **WHEN** система формирует publication payload
- **THEN** шаг завершается fail-closed до OData create/post
- **AND** diagnostics указывает на missing reusable account binding

