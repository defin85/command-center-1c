## MODIFIED Requirements

### Requirement: CC master-data hub MUST быть каноническим reusable-data layer для pool publication и bounded factual scopes
Система ДОЛЖНА (SHALL) хранить tenant-scoped канонический reusable-data слой в CC для pool publication и bounded factual scopes.

Минимальный гарантированный набор reusable entity families:
- `Party` (role-based: как минимум `our_organization` и `counterparty`);
- `Item`;
- `Contract` (строго owner-scoped к конкретному `counterparty`, без shared contract profiles);
- `TaxProfile` (минимум `vat_rate`, `vat_included`, `vat_code`);
- `GLAccount`;
- `GLAccountSet` как versioned grouped canonical profile для report/factual scopes.

Система НЕ ДОЛЖНА (SHALL NOT) требовать, чтобы оператор дублировал эти сущности вручную в каждой целевой ИБ перед каждым run или отдельно настраивал publication-only и factual-only каталоги reusable data.

#### Scenario: Publication и factual используют один canonical reusable-data layer
- **GIVEN** в CC сохранены canonical `Party`, `Item`, `Contract`, `TaxProfile`, `GLAccount` и `GLAccountSet` для tenant
- **WHEN** запускаются publication path и factual monitoring path
- **THEN** оба path используют один reusable-data layer как source-of-truth для canonical identity и bindings
- **AND** система не требует отдельный параллельный каталог account/reference данных для factual monitoring

### Requirement: Master-data resolve+upsert MUST поддерживать идемпотентный per-infobase binding с type-specific scope
Система ДОЛЖНА (SHALL) использовать режим `resolve+upsert` в reusable-data gate: при отсутствии binding создавать его детерминированно, при наличии — переиспользовать или обновлять в рамках type-specific ownership/policy.

Система ДОЛЖНА (SHALL) хранить binding канонической reusable сущности к конкретной ИБ в виде deterministic type-specific scope key:
- для `Party`: `(canonical_id, entity_type, database_id, ib_catalog_kind)`, где `ib_catalog_kind` как минимум `organization|counterparty`;
- для `Contract`: `(canonical_id, entity_type, database_id, owner_counterparty_id)`;
- для `Item/TaxProfile`: `(canonical_id, entity_type, database_id)`;
- для `GLAccount`: `(canonical_id, entity_type, database_id, chart_identity)`, где `chart_identity` однозначно определяет target chart of accounts;
- для будущих reusable entity types: deterministic scope, объявленный type registry.

Binding ДОЛЖЕН (SHALL) содержать ссылку на объект ИБ (`ib_ref_key` или эквивалент), если entity type materialize'ится в published IB object.

`GLAccountSet` МОЖЕТ (MAY) оставаться CC-side aggregate без собственного direct IB binding, если его runtime resolution детерминированно строится из member `GLAccount` bindings.

Система ДОЛЖНА (SHALL) выполнять resolve/sync идемпотентно по type-specific scope и НЕ ДОЛЖНА (SHALL NOT) создавать дубликаты binding при повторных запусках с тем же входом.

#### Scenario: GLAccount binding переиспользуется для publication и factual coverage
- **GIVEN** для canonical `GLAccount` уже существует валидный binding в target ИБ с target chart identity
- **WHEN** publication compile и factual preflight резолвят этот account
- **THEN** система использует один и тот же reusable binding
- **AND** новый duplicate binding для того же type-specific scope не создаётся

### Requirement: Master-data readiness preflight MUST возвращать полный список блокеров reusable-data coverage
Перед переходом к публикации или factual worker execution система ДОЛЖНА (SHALL) вычислять readiness/preflight coverage по target databases и возвращать machine-readable блокеры по canonical reusable data, включая:
- `Organization -> Party` bindings;
- required publication bindings;
- required `GLAccount` bindings для publication account fields;
- required member coverage для selected `GLAccountSet`.

#### Scenario: Missing GLAccount binding блокирует publication и factual execution
- **GIVEN** document policy или factual scope требует canonical `GLAccount`
- **AND** для части target databases отсутствует binding этого account в target chart
- **WHEN** выполняется readiness preflight
- **THEN** система возвращает structured blocker с `entity_type=gl_account` и `target_database_id`
- **AND** ни publication side effects, ни factual worker execution не стартуют

## ADDED Requirements

### Requirement: Reusable account entities MUST быть configuration-scoped и metadata-compatible
Система ДОЛЖНА (SHALL) хранить для `GLAccount` и `GLAccountSet` compatibility markers, достаточные для сопоставления reusable account entity с target business configuration identity и metadata snapshot provenance.

Система НЕ ДОЛЖНА (SHALL NOT) считать `GLAccount` или `GLAccountSet` globally compatible только на основании `canonical_id`, `chart_identity` или string account code.

#### Scenario: Account entity несовместима с target configuration и блокирует coverage
- **GIVEN** canonical `GLAccount` существует в hub
- **AND** target database относится к другой business configuration identity или metadata context
- **WHEN** система выполняет reusable-data coverage для publication или factual path
- **THEN** coverage завершается fail-closed как incompatible, даже если account code совпадает текстово
- **AND** оператор получает machine-readable диагностику несовместимого configuration scope

### Requirement: `GLAccountSet` MUST быть versioned и pin-able в runtime contexts
Система ДОЛЖНА (SHALL) хранить `GLAccountSet` как immutable revisioned profile, пригодный для pinning в readiness, checkpoints и runtime artifacts.

Система НЕ ДОЛЖНА (SHALL NOT) silently менять уже созданный runtime context только потому, что latest revision `GLAccountSet` была позже отредактирована.

#### Scenario: Поздняя правка latest revision не переписывает уже pinned runtime context
- **GIVEN** factual preflight или execution context уже использует pinned revision `GLAccountSet`
- **WHEN** оператор публикует новую revision того же account set
- **THEN** существующий runtime context сохраняет ранее pinned revision
- **AND** historical replay/readiness не пересчитываются silently на latest revision

### Requirement: Reusable-data type model MUST иметь explicit capability matrix
Система ДОЛЖНА (SHALL) для каждого reusable entity type объявлять capability matrix, включающую как минимум:
- manual upsert;
- direct IB binding;
- bootstrap import;
- inbound sync;
- outbound sync;
- token exposure;
- grouped profile membership.

Для первой итерации:
- `GLAccount` ДОЛЖЕН (SHALL) поддерживать manual upsert, direct binding, bootstrap import и token exposure;
- `GLAccount` НЕ ДОЛЖЕН (SHALL NOT) автоматически включаться в outbound sync или bidirectional mutation plan-of-accounts semantics;
- `GLAccountSet` ДОЛЖЕН (SHALL) оставаться CC-owned profile без direct IB binding и без sync policy в target ИБ.

#### Scenario: GLAccountSet не materialize'ится в target ИБ как sync entity
- **GIVEN** оператор создаёт или редактирует `GLAccountSet`
- **WHEN** система оценивает runtime capabilities этого entity type
- **THEN** `GLAccountSet` доступен как CC-side profile для selection/pinning
- **AND** не создаётся outbound sync intent в target ИБ только из-за сохранения profile revision

### Requirement: Reusable-data type model MUST оставаться additive и registry-driven
Система ДОЛЖНА (SHALL) поддерживать additive onboarding новых reusable entity types через registry/type-handler pattern, а не через создание отдельного каталога, отдельного binding storage или отдельного runtime path под каждый новый тип.

Type registry ДОЛЖЕН (SHALL) как минимум определять для каждого entity type:
- canonical identity contract;
- binding scope contract;
- compatibility markers;
- versioning/mutability contract;
- validation rules;
- supported token grammar;
- optional sync/bootstrap capabilities;
- runtime consumers, которым тип доступен.

Система НЕ ДОЛЖНА (SHALL NOT) требовать schema-less universal payload без type-specific validation только ради расширяемости.

#### Scenario: Новый reusable entity type подключается без второго ad hoc каталога
- **GIVEN** в систему добавляется новый reusable entity type после `GLAccount`
- **WHEN** команда расширяет hub новым type handler
- **THEN** canonical entity, binding и validation подключаются через existing reusable-data platform
- **AND** система не вводит отдельный параллельный workspace/runtime только для этого типа
