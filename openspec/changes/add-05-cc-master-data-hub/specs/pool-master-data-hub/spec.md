## ADDED Requirements
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
