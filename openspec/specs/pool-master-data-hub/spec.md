# pool-master-data-hub Specification

## Purpose
TBD - created by archiving change add-05-cc-master-data-hub. Update Purpose after archive.
## Requirements
### Requirement: CC master-data hub MUST быть каноническим источником для pool publication
Система ДОЛЖНА (SHALL) хранить tenant-scoped канонический master-data слой в CC для publication-сценариев pools.

Минимальный MVP-набор канонических сущностей:
- `Party` (role-based: как минимум `our_organization` и `counterparty`);
- `Item`;
- `Contract` (строго owner-scoped к конкретному `counterparty`, без shared contract profiles);
- `TaxProfile` (минимум `vat_rate`, `vat_included`, `vat_code`).

Система НЕ ДОЛЖНА (SHALL NOT) требовать, чтобы оператор дублировал эти сущности вручную в каждой целевой ИБ перед каждым run.

#### Scenario: Run использует master-data из CC как source-of-truth
- **GIVEN** в CC сохранены канонические `Party`, `Item`, `Contract`, `TaxProfile` для tenant
- **WHEN** запускается pool run с publication path
- **THEN** runtime использует канонические сущности CC как source-of-truth для resolve/sync
- **AND** не требует ручного предварительного заполнения всех справочников в каждой ИБ

### Requirement: Master-data resolve+upsert MUST поддерживать идемпотентный per-infobase binding
Система ДОЛЖНА (SHALL) использовать режим `resolve+upsert` в pre-publication gate: при отсутствии binding создавать его детерминированно, при наличии — переиспользовать или обновлять в рамках политики ownership.

Система ДОЛЖНА (SHALL) хранить binding канонической сущности к конкретной ИБ в виде ключа:
- для `Party`: `(canonical_id, entity_type, database_id, ib_catalog_kind)`, где `ib_catalog_kind` как минимум `organization|counterparty`;
- для `Contract`: `(canonical_id, entity_type, database_id, owner_counterparty_id)`;
- для остальных сущностей MVP: `(canonical_id, entity_type, database_id)`.

Binding ДОЛЖЕН (SHALL) содержать ссылку на объект ИБ (`ib_ref_key` или эквивалент).

Система ДОЛЖНА (SHALL) выполнять resolve/sync идемпотентно по этой паре и НЕ ДОЛЖНА (SHALL NOT) создавать дубликаты binding при повторных запусках с тем же входом.

#### Scenario: Повторный resolve/sync переиспользует существующий binding
- **GIVEN** для `(canonical_id, entity_type, database_id)` уже существует валидный binding
- **WHEN** следующий run выполняет pre-publication resolve/sync
- **THEN** система переиспользует существующий binding
- **AND** новый дублирующий binding не создаётся

#### Scenario: Отсутствующий binding создаётся детерминированно
- **GIVEN** для канонической сущности отсутствует binding в конкретной target ИБ
- **WHEN** runtime выполняет pre-publication resolve/sync
- **THEN** система создаёт binding и фиксирует `ib_ref_key` в artifact
- **AND** последующие повторные вызовы с тем же входом возвращают тот же resolved результат

#### Scenario: Один Party использует role-specific bindings в одной ИБ
- **GIVEN** один `Party` участвует в run одновременно в ролях `our_organization` и `counterparty`
- **WHEN** runtime выполняет pre-publication resolve+upsert
- **THEN** система использует/создаёт отдельные bindings для `ib_catalog_kind=organization` и `ib_catalog_kind=counterparty`
- **AND** publication payload использует binding, соответствующий роли документа

#### Scenario: Contract binding не переиспользуется между разными counterparty
- **GIVEN** договор канонически принадлежит `counterparty=A` и уже имеет binding в target ИБ
- **WHEN** runtime пытается использовать этот договор для документа с `counterparty=B`
- **THEN** binding для `counterparty=A` не переиспользуется
- **AND** выполнение завершается fail-closed с machine-readable конфликтом owner-scope

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

