# pool-master-data-hub Specification

## Purpose
TBD - created by archiving change add-05-cc-master-data-hub. Update Purpose after archive.
## Requirements
### Requirement: CC master-data hub MUST быть каноническим источником для pool publication
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

### Requirement: Master-data resolve+upsert MUST поддерживать идемпотентный per-infobase binding
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

### Requirement: Master-data conflicts MUST блокировать publication fail-closed
Система ДОЛЖНА (SHALL) останавливать run до `pool.publication_odata`, если resolve/sync возвращает конфликт или неоднозначность соответствий master-data.

Система ДОЛЖНА (SHALL) возвращать machine-readable diagnostics минимум с полями:
- `error_code`;
- `entity_type`;
- `canonical_id`;
- `target_database_id`;
- `detail`.

Минимальные коды ошибок MVP:
- `MASTER_DATA_ENTITY_NOT_FOUND`;
- `MASTER_DATA_BINDING_AMBIGUOUS`;
- `MASTER_DATA_BINDING_CONFLICT`.

#### Scenario: Неоднозначный match блокирует переход к публикации
- **GIVEN** в target ИБ для канонической сущности обнаружено неоднозначное соответствие
- **WHEN** runtime выполняет master-data resolve/sync gate
- **THEN** run завершается fail-closed до OData side effects
- **AND** diagnostics содержит `error_code=MASTER_DATA_BINDING_AMBIGUOUS` и контекст проблемной ИБ

### Requirement: Master-data readiness preflight MUST возвращать полный список блокеров публикации
Перед переходом к публикации система MUST вычислять readiness preflight по target databases и возвращать machine-readable блокеры по canonical master-data и Organization->Party bindings.

#### Scenario: Отсутствующие bindings блокируют публикацию с диагностикой remediation-ready
- **GIVEN** run готов к публикации и для части target organizations отсутствуют `master_party` bindings
- **WHEN** выполняется readiness preflight
- **THEN** система возвращает structured blockers с указанием `organization_id`, `database_id` и типа отсутствующей связи
- **AND** переход к `publication_odata` блокируется fail-closed

### Requirement: Readiness snapshot MUST быть детерминированным и пригодным для повторной проверки
Readiness результат MUST сохраняться как стабильный snapshot для run inspection/retry, чтобы оператор видел одинаковую причину блокировки до устранения входных данных.

#### Scenario: Повторный preflight без изменений возвращает тот же набор блокеров
- **GIVEN** данные master-data и bindings не менялись
- **WHEN** preflight выполняется повторно для того же run контекста
- **THEN** snapshot blockers остаётся детерминированно эквивалентным предыдущему

### Requirement: Master-data hub MUST резолвить topology participants через Organization->Party binding
Система ДОЛЖНА (SHALL) использовать `Organization.master_party` как canonical binding topology participant-а для
`document_policy` aliases вида `master_data.party.edge.parent.*`, `master_data.party.edge.child.*` и
`master_data.contract.<id>.edge.parent|child.ref`.

При resolution:
- `edge.parent` ДОЛЖЕН (SHALL) адресовать parent organization активного topology edge;
- `edge.child` ДОЛЖЕН (SHALL) адресовать child organization активного topology edge;
- qualifier `organization` ДОЛЖЕН (SHALL) требовать `master_party.is_our_organization=true`;
- qualifier `counterparty` ДОЛЖЕН (SHALL) требовать `master_party.is_counterparty=true`;
- contract alias ДОЛЖЕН (SHALL) использовать canonical id соответствующего participant-а как
  `owner_counterparty_canonical_id` при rewrite в static token grammar.

#### Scenario: Contract owner canonical id выводится из child participant
- **GIVEN** `document_policy` содержит `master_data.contract.osnovnoy.edge.child.ref`
- **AND** child organization текущего edge имеет `master_party.canonical_id=dom-lesa`
- **WHEN** runtime резолвит topology-aware alias
- **THEN** resulting static token равен `master_data.contract.osnovnoy.dom-lesa.ref`
- **AND** downstream master-data resolve использует обычный contract binding scope

### Requirement: Non-participant master-data objects MUST продолжать резолвиться через canonical static bindings
Система ДОЛЖНА (SHALL) продолжать резолвить `item` и `tax_profile` через существующий static canonical token
contract без topology participant indirection.

Система НЕ ДОЛЖНА (SHALL NOT) пытаться выводить `item` или `tax_profile` из `edge.parent` / `edge.child`
только на основании topology structure.

#### Scenario: Static item token bypasses topology participant resolution
- **GIVEN** `document_policy` содержит `master_data.item.packing-service.ref`
- **WHEN** runtime выполняет readiness/compile path
- **THEN** система не требует `participant_side` или `required_role` для этого token-а
- **AND** resulting readiness/gate path использует existing canonical binding semantics для `item`

### Requirement: Topology participant readiness MUST блокировать publication при missing binding или role
Система ДОЛЖНА (SHALL) блокировать preview/create-run fail-closed, если topology-aware alias требует participant,
для которого:
- отсутствует `Organization->Party` binding;
- bound `master_party` не содержит требуемую роль.

Система ДОЛЖНА (SHALL) возвращать machine-readable blockers минимум с полями:
- `code`;
- `detail`;
- `organization_id`;
- `database_id`;
- `edge_ref`;
- `participant_side`;
- `required_role`.

Минимальные коды ошибок:
- `MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING`
- `MASTER_DATA_PARTY_ROLE_MISSING`

#### Scenario: Missing child counterparty role блокирует receipt policy compile
- **GIVEN** `document_policy` использует `master_data.party.edge.child.counterparty.ref`
- **AND** child organization текущего edge имеет `master_party`, но у него `is_counterparty=false`
- **WHEN** runtime выполняет readiness/compile path
- **THEN** preview/create-run завершается fail-closed
- **AND** diagnostics содержит `MASTER_DATA_PARTY_ROLE_MISSING`
- **AND** blocker указывает `participant_side=child` и `required_role=counterparty`

#### Scenario: Missing parent organization binding блокирует realization policy compile
- **GIVEN** `document_policy` использует `master_data.party.edge.parent.organization.ref`
- **AND** parent organization текущего edge не имеет `master_party`
- **WHEN** runtime выполняет readiness/compile path
- **THEN** preview/create-run завершается fail-closed
- **AND** diagnostics содержит `MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING`
- **AND** blocker указывает `participant_side=parent` и `required_role=organization`

### Requirement: Reusable-data type model MUST быть registry-driven и executable
Система ДОЛЖНА (SHALL) описывать reusable-data entity types через backend-owned executable registry/type-handler contract, а не через набор несвязанных enum/switch списков.

Registry ДОЛЖЕН (SHALL) определять как минимум:
- canonical entity key;
- binding scope contract;
- token exposure;
- bootstrap eligibility;
- sync/outbox eligibility;
- runtime consumers.

Backend-owned registry ДОЛЖЕН (SHALL) materialize-иться в generated shared contract/schema для `contracts/**` и frontend.
Система НЕ ДОЛЖНА (SHALL NOT) поддерживать handwritten duplicated registry definition в UI как parallel source-of-truth.

#### Scenario: Frontend и backend читают один registry contract
- **GIVEN** backend registry уже определяет reusable-data types и их capabilities
- **WHEN** contracts pipeline публикует generated registry artifact
- **THEN** frontend token catalogs и backend runtime gating используют одно и то же capability решение
- **AND** новая capability policy не требует ручной синхронизации нескольких enum lists

#### Scenario: Новый reusable entity type подключается через handler, а не через scattered enum edits
- **GIVEN** команда добавляет новый reusable entity type после foundation change
- **WHEN** она регистрирует type handler в executable registry
- **THEN** система получает один source-of-truth для routing и validation
- **AND** подключение не требует создания второго ad hoc каталога reusable data

### Requirement: Reusable-data capabilities MUST default fail-closed
Система ДОЛЖНА (SHALL) трактовать отсутствие явно объявленной capability как запрет на соответствующий runtime path.

Система НЕ ДОЛЖНА (SHALL NOT) считать наличие `entity_type` в enum, API namespace или binding storage достаточным основанием для:
- sync enqueue;
- outbox fan-out;
- bootstrap import;
- token exposure;
- mutating runtime actions.

#### Scenario: Новый entity type не становится исполнимым только из-за появления в enum
- **GIVEN** entity type добавлен в backend API surface, но registry capability для sync/outbox не объявлена
- **WHEN** runtime оценивает eligibility этого типа
- **THEN** sync enqueue и outbox fan-out остаются заблокированными
- **AND** система завершает проверку fail-closed вместо implicit enablement

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

