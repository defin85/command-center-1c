# pool-master-data-hub-ui Specification

## Purpose
TBD - created by archiving change add-06-pool-master-data-hub-ui. Update Purpose after archive.
## Requirements
### Requirement: Pools MUST предоставлять отдельный master-data workspace для оператора
Система ДОЛЖНА (SHALL) предоставлять отдельную страницу `/pools/master-data` как рабочее пространство для управления каноническими master-data сущностями в tenant scope.

Система ДОЛЖНА (SHALL) поддерживать в workspace минимум пять рабочих зон:
- `Party`;
- `Item`;
- `Contract`;
- `TaxProfile`;
- `Bindings`.

Workspace ДОЛЖЕН (SHALL) быть доступен из основного меню Pools и работать в рамках текущего tenant context.

#### Scenario: Оператор открывает master-data workspace из меню Pools
- **GIVEN** пользователь имеет доступ к Pools и выбран tenant context
- **WHEN** пользователь открывает `/pools/master-data`
- **THEN** система отображает рабочие зоны `Party`, `Item`, `Contract`, `TaxProfile`, `Bindings`
- **AND** операции выполняются в tenant scope без cross-tenant данных

### Requirement: Master-data API MUST использовать Problem Details контракт для ошибок
Система ДОЛЖНА (SHALL) возвращать ошибки новых endpoint-ов master-data workspace в формате `application/problem+json`.

Problem payload ДОЛЖЕН (SHALL) включать поля `type`, `title`, `status`, `detail`, `code`.

Система ДОЛЖНА (SHALL) публиковать endpoint-ы master-data workspace в namespace `/api/v2/pools/master-data/` для групп:
- `parties`,
- `items`,
- `contracts`,
- `tax-profiles`,
- `bindings`,
с операциями list/get/upsert для каждой группы.

#### Scenario: Конфликт binding scope возвращается как Problem Details
- **GIVEN** оператор сохраняет `Binding`, который нарушает уникальность scope
- **WHEN** backend отклоняет mutating запрос
- **THEN** response content-type равен `application/problem+json`
- **AND** payload содержит machine-readable `code`

#### Scenario: Workspace использует канонический namespace master-data endpoint-ов
- **GIVEN** оператор открывает tab `Party` в `/pools/master-data`
- **WHEN** UI запрашивает список canonical `Party`
- **THEN** запрос выполняется в namespace `/api/v2/pools/master-data/parties/`
- **AND** для create/edit используется `.../parties/upsert/`

### Requirement: Workspace MUST enforce доменные инварианты canonical сущностей
Система ДОЛЖНА (SHALL) при create/edit через UI соблюдать инварианты:
- `Party` имеет хотя бы одну роль (`our_organization` или `counterparty`);
- `Contract` всегда привязан к owner `counterparty` (owner-scoped);
- `TaxProfile` в MVP содержит только `vat_rate`, `vat_included`, `vat_code`.

Система НЕ ДОЛЖНА (SHALL NOT) позволять отправку формы, которая нарушает эти инварианты.

#### Scenario: UI блокирует создание Contract без owner counterparty
- **GIVEN** оператор открыл форму создания `Contract`
- **WHEN** owner counterparty не выбран или выбран `Party` без роли `counterparty`
- **THEN** UI блокирует submit
- **AND** показывает понятную ошибку валидации до backend round-trip

### Requirement: Organization and Party MUST иметь явную связь без конкуренции source-of-truth
Система ДОЛЖНА (SHALL) поддерживать явную связь `Organization <-> Party` (MVP один-к-одному), чтобы:
- `Organization` оставался владельцем topology/pool-catalog контекста;
- `Party` оставался владельцем канонических master-data реквизитов publication слоя.

Система ДОЛЖНА (SHALL) требовать, чтобы связанный с `Organization` `Party` имел роль `our_organization`.

#### Scenario: Организация связывается только с Party в роли our_organization
- **GIVEN** оператор настраивает связь `Organization -> Party`
- **WHEN** выбранный `Party` не имеет роли `our_organization`
- **THEN** система отклоняет сохранение связи
- **AND** возвращает machine-readable ошибку валидации

### Requirement: Workspace MUST поддерживать role-specific и owner-scoped bindings
Система ДОЛЖНА (SHALL) предоставлять в зоне `Bindings` явное управление scope-ключами binding:
- для `Party`: `(canonical_id, entity_type, database_id, ib_catalog_kind)`;
- для `Contract`: `(canonical_id, entity_type, database_id, owner_counterparty_id)`;
- для `Item/TaxProfile`: `(canonical_id, entity_type, database_id)`.

Система ДОЛЖНА (SHALL) отображать machine-readable конфликтные ответы backend без потери введённых оператором данных.

#### Scenario: Один Party на одну ИБ имеет два binding по ролям
- **GIVEN** один `Party` участвует как `organization` и `counterparty`
- **WHEN** оператор настраивает bindings для одной target ИБ
- **THEN** система позволяет сохранить отдельные binding для каждой роли
- **AND** UI явно показывает роль каждого binding в списке

### Requirement: Document policy authoring MUST поддерживать guided master-data token picker
Система ДОЛЖНА (SHALL) в `/pools/catalog` предоставлять guided token picker для `field_mapping` и `table_parts_mapping` в `document_policy` builder.

Token picker ДОЛЖЕН (SHALL) генерировать токены совместимого формата:
- `master_data.party.<canonical_id>.<organization|counterparty>.ref`;
- `master_data.item.<canonical_id>.ref`;
- `master_data.contract.<canonical_id>.<owner_counterparty_canonical_id>.ref`;
- `master_data.tax_profile.<canonical_id>.ref`.

#### Scenario: Оператор выбирает номенклатуру через token picker
- **GIVEN** оператор редактирует `table_parts_mapping` документа в policy builder
- **WHEN** он выбирает поле табличной части и выбирает `Item` в token picker
- **THEN** система подставляет валидный token `master_data.item.<canonical_id>.ref`
- **AND** оператору не требуется ручной ввод token строки

### Requirement: Pool runs inspection MUST показывать operator-facing диагностику master-data gate
Система ДОЛЖНА (SHALL) отображать на `/pools/runs` отдельный блок `Master Data Gate` с summary и diagnostics:
- `status`, `mode`;
- `targets_count`, `bindings_count`;
- `error_code`, `detail`;
- проблемный `entity_type/canonical_id/target_database_id` (если есть ошибка).

Система ДОЛЖНА (SHALL) отображать remediation hint на основе machine-readable `error_code`.

#### Scenario: Ошибка gate отображается без ручного анализа raw JSON
- **GIVEN** run завершился fail-closed на `pool.master_data_gate`
- **WHEN** оператор открывает run report на `/pools/runs`
- **THEN** система показывает код/детали ошибки и контекст сущности/ИБ в отдельной карточке
- **AND** оператор получает action-oriented подсказку по исправлению

### Requirement: Pool master-data workspace MUST предоставлять операторский Bootstrap Import from IB wizard
Система ДОЛЖНА (SHALL) в `/pools/master-data` предоставить отдельную рабочую зону `Bootstrap Import` для первичного импорта canonical master-data из выбранной ИБ.

Wizard ДОЛЖЕН (SHALL) как минимум поддерживать шаги:
1. выбор базы и entity scope;
2. preflight;
3. dry-run summary;
4. execute.

#### Scenario: Оператор запускает bootstrap wizard из master-data workspace
- **GIVEN** пользователь открыл `/pools/master-data` в активном tenant context
- **WHEN** он переходит в рабочую зону `Bootstrap Import`
- **THEN** система отображает wizard с выбором базы и сущностей для импорта
- **AND** запуск выполняется через канонический v2 API bootstrap import

### Requirement: UI MUST enforce preflight/dry-run gate before execute
Система ДОЛЖНА (SHALL) блокировать кнопку execute, пока не завершены preflight и dry-run выбранного bootstrap scope.

Система НЕ ДОЛЖНА (SHALL NOT) отправлять execute-запрос при fail-результате preflight/dry-run.

#### Scenario: Провал preflight блокирует execute в UI
- **GIVEN** preflight вернул fail-closed ошибку для выбранной базы
- **WHEN** оператор находится на шаге запуска
- **THEN** execute action недоступен
- **AND** UI показывает operator-facing причину блокировки

#### Scenario: Dry-run summary обязателен перед запуском execute
- **GIVEN** preflight успешно завершён
- **WHEN** dry-run ещё не выполнен
- **THEN** UI не отправляет execute-запрос
- **AND** оператору предлагается сначала получить dry-run summary

### Requirement: UI MUST показывать прогресс, итог и операторские действия по bootstrap job
Система ДОЛЖНА (SHALL) отображать live status bootstrap job:
- текущий статус;
- прогресс по chunk-ам;
- counters `created/updated/skipped/failed`;
- последний код/деталь ошибки (если есть).

Система ДОЛЖНА (SHALL) поддерживать операторские действия `cancel` и `retry failed chunks` в соответствии со статусом job.

#### Scenario: Частично неуспешный import позволяет retry только failed chunks
- **GIVEN** bootstrap job завершился с частичными ошибками
- **WHEN** оператор запускает `retry failed chunks`
- **THEN** UI отправляет соответствующий API action
- **AND** повторный запуск ограничивается только ранее failed chunk-ами

#### Scenario: UI сохраняет контекст и не теряет ввод при ошибке API
- **GIVEN** bootstrap mutating action завершился ошибкой Problem Details
- **WHEN** UI отображает ошибку
- **THEN** выбранные оператором параметры scope/шаг wizard сохраняются
- **AND** оператор может исправить условия и повторить действие без повторного ввода всех данных

### Requirement: Pools master-data workspace MUST показывать readiness checklist для run публикации
UI master-data workspace MUST предоставлять оператору readiness checklist перед запуском/подтверждением публикации, включая отсутствующие canonical сущности, bindings и неполноту policy profile.

#### Scenario: Оператор видит блокеры и может перейти к их устранению
- **GIVEN** readiness preflight вернул блокеры
- **WHEN** оператор открывает run inspection в UI
- **THEN** интерфейс показывает список блокеров в операторском формате
- **AND** для каждого блокера доступны remediation переходы в соответствующий раздел workspace

### Requirement: Run inspection UI MUST отображать результат OData verification после публикации
После завершения публикации UI MUST показывать verification summary по опубликованным refs, включая количество проверенных документов и mismatch counters.

#### Scenario: UI показывает итог сверки документов по OData
- **GIVEN** run завершён и verifier выполнил post-run проверку
- **WHEN** оператор открывает report
- **THEN** он видит `verification_status`, `verified_documents_count` и `mismatch_count`
- **AND** может раскрыть детали mismatches без чтения raw JSON

