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

Для `GLAccount` `ib_ref_key` / `Ref_Key` ДОЛЖЕН (SHALL) использоваться только как per-infobase binding surface и НЕ ДОЛЖЕН (SHALL NOT) трактоваться как canonical или cross-infobase identity.

Для `GLAccount` поле `chart_identity` ДОЛЖНО (SHALL) быть first-class persisted scope field, участвующим в uniqueness и lookup contract. Система НЕ ДОЛЖНА (SHALL NOT) хранить `chart_identity` только в opaque metadata, если от него зависит idempotent resolve/binding behavior.

`GLAccountSet` МОЖЕТ (MAY) оставаться CC-side aggregate без собственного direct IB binding, если его runtime resolution детерминированно строится из member `GLAccount` bindings.

Система ДОЛЖНА (SHALL) выполнять resolve/sync идемпотентно по type-specific scope и НЕ ДОЛЖНА (SHALL NOT) создавать дубликаты binding при повторных запусках с тем же входом.

#### Scenario: GLAccount binding переиспользуется для publication и factual coverage
- **GIVEN** для canonical `GLAccount` уже существует валидный binding в target ИБ с target chart identity
- **WHEN** publication compile и factual preflight резолвят этот account
- **THEN** система использует один и тот же reusable binding
- **AND** новый duplicate binding для того же type-specific scope не создаётся

#### Scenario: `chart_identity` участвует в persisted uniqueness contract
- **GIVEN** оператор сохраняет `GLAccount` binding для `(canonical_id=sales-revenue, database_id=db-1, chart_identity=ChartOfAccounts_Хозрасчетный)`
- **WHEN** система повторно получает тот же scope
- **THEN** persisted lookup использует тот же first-class scope key и не создаёт duplicate binding
- **AND** `chart_identity` не резолвится только из metadata blob или UI convention

### Requirement: `GLAccount` canonical identity MUST быть отделена от per-infobase object refs
Система ДОЛЖНА (SHALL) трактовать `GLAccount` в CC как tenant-scoped canonical semantic account, а не как локальный объект конкретной ИБ.

Система НЕ ДОЛЖНА (SHALL NOT) использовать `ib_ref_key` / `Ref_Key` как canonical identity или как cross-infobase key для reusable account entity.

Для predefined accounts система МОЖЕТ (MAY) хранить и использовать `PredefinedDataName` как дополнительный compatibility/admission marker внутри одного `chart_identity`, но НЕ ДОЛЖНА (SHALL NOT):
- заменять им `canonical_id` как operator-facing identity;
- требовать `PredefinedDataName` для non-predefined account surfaces;
- считать его достаточным без target-specific binding и metadata/published-surface evidence.

#### Scenario: Один predefined account имеет разные `Ref_Key` в разных ИБ, но остаётся одним canonical `GLAccount`
- **GIVEN** две target ИБ публикуют один и тот же predefined счёт с одинаковыми `Code`, `Description` и `PredefinedDataName`
- **AND** их `Ref_Key` различается между ИБ
- **WHEN** система сохраняет canonical reusable account и соответствующие bindings
- **THEN** в CC существует один canonical `GLAccount`
- **AND** каждая ИБ получает собственный binding с локальным `Ref_Key`
- **AND** `Ref_Key` не становится cross-infobase identity этого account

#### Scenario: Publication использует только target-local binding ref
- **GIVEN** canonical `GLAccount` уже сопоставлен с несколькими target ИБ
- **WHEN** publication или factual runtime формирует target-specific payload
- **THEN** runtime использует `Ref_Key` только из binding выбранной target ИБ
- **AND** не переносит foreign `Ref_Key` из другой ИБ

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

Operator-facing compatibility class для reusable account entities ДОЛЖЕН (SHALL) использовать:
- `config_name`;
- `config_version`;
- `chart_identity`.

Runtime admission/pinning contract ДОЛЖЕН (SHALL) хранить как минимум:
- `metadata_catalog_snapshot_id`;
- `catalog_version`;
- `metadata_hash`;
- `provenance_database_id`;
- `confirmed_at`.

Совпадение `config_name + config_version + chart_identity` ДОЛЖНО (SHALL) использоваться для operator-facing grouping/discovery, но НЕ ДОЛЖНО (SHALL NOT) само по себе считаться достаточным runtime admission signal.
Publication/factual coverage ДОЛЖНЫ (SHALL) дополнительно требовать pinned metadata provenance и positive published-surface evidence для target infobase.

В этом change canonical identity `GLAccount` остаётся tenant-scoped и не дробится по target infobase. Compatibility class и pinned provenance управляют admission/use against target ИБ, а не создают отдельную canonical identity на каждый `database_id` или `Ref_Key`.

Система НЕ ДОЛЖНА (SHALL NOT) считать `GLAccount` или `GLAccountSet` globally compatible только на основании `canonical_id`, `chart_identity`, `PredefinedDataName`, string account code или локального `Ref_Key`.
Система НЕ ДОЛЖНА (SHALL NOT) использовать `catalog_version` или `metadata_hash` как единственный operator-facing compatibility key без stable business/configuration semantics.

#### Scenario: Account entity несовместима с target configuration и блокирует coverage
- **GIVEN** canonical `GLAccount` существует в hub
- **AND** target database относится к другой business configuration identity или metadata context
- **WHEN** система выполняет reusable-data coverage для publication или factual path
- **THEN** coverage завершается fail-closed как incompatible, даже если account code совпадает текстово
- **AND** оператор получает machine-readable диагностику несовместимого configuration scope

#### Scenario: Persisted provenance pin-ит metadata context без подмены compatibility key
- **GIVEN** `GLAccountSet` already pinned в runtime context для `config_name=Accounting`, `config_version=3.0.170`, `chart_identity=ChartOfAccounts_Хозрасчетный`
- **WHEN** система сохраняет readiness/checkpoint artifact
- **THEN** artifact содержит stable compatibility key и pinned metadata provenance (`snapshot_id`, `catalog_version`, `metadata_hash`)
- **AND** оператор и runtime не зависят от opaque metadata hash как от единственного идентификатора совместимости

#### Scenario: Совпавший compatibility class без published-surface evidence не даёт runtime admission
- **GIVEN** reusable `GLAccount` и target database имеют одинаковые `config_name`, `config_version` и `chart_identity`
- **AND** pinned metadata snapshot или published surface target infobase не подтверждает доступность требуемого chart/register contract
- **WHEN** система выполняет publication или factual coverage
- **THEN** admission завершается fail-closed
- **AND** оператор получает диагностику, что compatibility class совпал, но runtime evidence недостаточен

### Requirement: `GLAccountSet` MUST быть versioned и pin-able в runtime contexts
Система ДОЛЖНА (SHALL) хранить `GLAccountSet` как immutable revisioned profile, пригодный для pinning в readiness, checkpoints и runtime artifacts.

Система НЕ ДОЛЖНА (SHALL NOT) silently менять уже созданный runtime context только потому, что latest revision `GLAccountSet` была позже отредактирована.

Revision/member contract ДОЛЖЕН (SHALL) быть first-class persisted surface с явными revision rows и member rows. Система НЕ ДОЛЖНА (SHALL NOT) полагаться только на mutable metadata blob как на единственный source-of-truth для revision membership.

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

Executable reusable-data registry ДОЛЖЕН (SHALL) быть source-of-truth не только для schema-level metadata, но и для routing seams:
- gate/token parsing;
- token picker catalogs;
- bootstrap dependency ordering;
- sync enqueue/outbox routing;
- readiness coverage selection.

Система НЕ ДОЛЖНА (SHALL NOT) требовать schema-less universal payload без type-specific validation только ради расширяемости.
Система НЕ ДОЛЖНА (SHALL NOT) считать scattered enum/switch ветки в gate, sync runtime, bootstrap order или UI picker primary механизмом onboarding нового reusable entity type; такие ветки МОГУТ (MAY) существовать только как временные compatibility wrappers на переходном периоде.

#### Scenario: Новый reusable entity type подключается без второго ad hoc каталога
- **GIVEN** в систему добавляется новый reusable entity type после `GLAccount`
- **WHEN** команда расширяет hub новым type handler
- **THEN** canonical entity, binding и validation подключаются через existing reusable-data platform
- **AND** система не вводит отдельный параллельный workspace/runtime только для этого типа

#### Scenario: Registry управляет routing seams без скрытого enum drift
- **GIVEN** для `GLAccount` объявлены registry metadata, token grammar и sync/bootstrap capabilities
- **WHEN** система строит gate parsing, token picker, bootstrap order и runtime routing
- **THEN** эти seams читают executable registry как source-of-truth
- **AND** отсутствие отдельной ручной правки в scattered enum list не создаёт скрытый partial-onboarding gap
