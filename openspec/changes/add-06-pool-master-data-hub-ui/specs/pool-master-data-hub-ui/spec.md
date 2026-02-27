## ADDED Requirements
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

#### Scenario: Конфликт binding scope возвращается как Problem Details
- **GIVEN** оператор сохраняет `Binding`, который нарушает уникальность scope
- **WHEN** backend отклоняет mutating запрос
- **THEN** response content-type равен `application/problem+json`
- **AND** payload содержит machine-readable `code`

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

Система МОЖЕТ (MAY) оставлять raw-json режим для advanced сценариев.

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
