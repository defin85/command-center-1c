## ADDED Requirements
### Requirement: CC master-data hub MUST быть каноническим источником для pool publication
Система ДОЛЖНА (SHALL) хранить tenant-scoped канонический master-data слой в CC для publication-сценариев pools.

Минимальный MVP-набор канонических сущностей:
- `Party` (role-based: как минимум `our_organization` и `counterparty`);
- `Item`;
- `Contract`;
- `TaxProfile`.

Система НЕ ДОЛЖНА (SHALL NOT) требовать, чтобы оператор дублировал эти сущности вручную в каждой целевой ИБ перед каждым run.

#### Scenario: Run использует master-data из CC как source-of-truth
- **GIVEN** в CC сохранены канонические `Party`, `Item`, `Contract`, `TaxProfile` для tenant
- **WHEN** запускается pool run с publication path
- **THEN** runtime использует канонические сущности CC как source-of-truth для resolve/sync
- **AND** не требует ручного предварительного заполнения всех справочников в каждой ИБ

### Requirement: Master-data resolve/sync MUST поддерживать идемпотентный per-infobase binding
Система ДОЛЖНА (SHALL) хранить binding канонической сущности к конкретной ИБ в виде пары `(canonical_id, entity_type, database_id)` с ссылкой на объект ИБ (`ib_ref_key` или эквивалент).

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
