## MODIFIED Requirements

### Requirement: CC master-data hub MUST быть каноническим reusable-data layer для pool publication
Система ДОЛЖНА (SHALL) хранить tenant-scoped канонический reusable-data слой в CC для publication-сценариев pools.

Минимальный поддерживаемый набор reusable entity families после этого change:
- `Party`;
- `Item`;
- `Contract`;
- `TaxProfile`;
- `GLAccount`;
- `GLAccountSet` как versioned reusable profile с draft и published revisions.

Система НЕ ДОЛЖНА (SHALL NOT) требовать отдельный ad hoc каталог reusable accounts вне канонического hub.

#### Scenario: Reusable accounts живут в том же hub, что и publication master-data
- **GIVEN** в CC сохранены canonical `Party`, `Item`, `Contract`, `TaxProfile`, `GLAccount` и `GLAccountSet`
- **WHEN** оператор работает с reusable data для pool publication
- **THEN** accounts доступны в том же canonical hub
- **AND** система не требует отдельного каталога для account references

### Requirement: Master-data resolve+upsert MUST поддерживать идемпотентный per-infobase binding с type-specific scope
Система ДОЛЖНА (SHALL) использовать режим `resolve+upsert` для reusable-data gate и хранить binding канонической reusable сущности к конкретной ИБ в deterministic type-specific scope.

Binding scope ключи ДОЛЖНЫ (SHALL) включать как минимум:
- для `Party`: `(canonical_id, entity_type, database_id, ib_catalog_kind)`;
- для `Contract`: `(canonical_id, entity_type, database_id, owner_counterparty_id)`;
- для `Item/TaxProfile`: `(canonical_id, entity_type, database_id)`;
- для `GLAccount`: `(canonical_id, entity_type, database_id, chart_identity)`.

Для `GLAccount` `ib_ref_key` / `Ref_Key` ДОЛЖЕН (SHALL) использоваться только как per-infobase binding surface и НЕ ДОЛЖЕН (SHALL NOT) трактоваться как canonical или cross-infobase identity.

#### Scenario: `chart_identity` участвует в deterministic GLAccount binding scope
- **GIVEN** canonical `GLAccount` уже имеет binding для `(database_id=db-1, chart_identity=ChartOfAccounts_Хозрасчетный)`
- **WHEN** система повторно резолвит тот же scope
- **THEN** она переиспользует существующий binding
- **AND** не создаёт duplicate row только из-за того, что `chart_identity` был hidden metadata instead of first-class field

#### Scenario: `Ref_Key` остаётся target-local, а не canonical identity
- **GIVEN** один и тот же canonical `GLAccount` связан с несколькими target ИБ
- **WHEN** runtime или оператор читает bindings
- **THEN** каждая ИБ имеет собственный target-local `Ref_Key`
- **AND** этот `Ref_Key` не используется как cross-infobase key reusable account entity

## ADDED Requirements

### Requirement: Reusable account entities MUST иметь explicit compatibility contract
Система ДОЛЖНА (SHALL) хранить для `GLAccount` и `GLAccountSet` operator-facing compatibility class:
- `config_name`;
- `config_version`;
- `chart_identity`.

Система ДОЛЖНА (SHALL) отделять этот compatibility class от runtime admission provenance, который может требовать pinned metadata snapshot и published-surface evidence.

#### Scenario: Совпадение compatibility class не подменяет runtime provenance
- **GIVEN** reusable account и target database имеют одинаковые `config_name`, `config_version` и `chart_identity`
- **WHEN** система оценивает только operator-facing compatibility
- **THEN** результат можно использовать для grouping/discovery
- **AND** runtime admission остаётся отдельной проверкой, а не implicit success

### Requirement: `GLAccountSet` MUST быть versioned reusable profile с immutable revisions
Система ДОЛЖНА (SHALL) хранить `GLAccountSet` как profile с current draft и published immutable revisions.

Система НЕ ДОЛЖНА (SHALL NOT) мутировать уже опубликованную revision через generic `upsert`.

#### Scenario: Publish создаёт новую immutable revision
- **GIVEN** оператор подготовил draft `GLAccountSet`
- **WHEN** он выполняет `publish`
- **THEN** система создаёт новую immutable revision
- **AND** дальнейшие edits изменяют draft/profile state, а не уже опубликованную revision

#### Scenario: Upsert обновляет draft, но не published revision
- **GIVEN** у `GLAccountSet` уже есть опубликованная revision
- **WHEN** оператор редактирует profile через `upsert`
- **THEN** меняется current draft
- **AND** ранее опубликованная revision остаётся неизменной
