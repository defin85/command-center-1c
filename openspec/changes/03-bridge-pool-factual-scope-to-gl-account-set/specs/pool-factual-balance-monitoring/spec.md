## MODIFIED Requirements

### Requirement: Factual balance projection MUST использовать реальные документы и регистры ИБ как source of truth
Система ДОЛЖНА (SHALL) строить factual balance projection по реальным документам и регистрам ИБ, а не по ожидаемым суммам из runtime distribution artifacts.

В первой итерации бухгалтерским эталоном ДОЛЖЕН (SHALL) считаться отчёт `Продажи`, построенный на bounded чтении `РегистрБухгалтерии.Хозрасчетный.Обороты(...)`, `РегистрСведений.ДанныеПервичныхДокументов` и связанных документов `РеализацияТоваровУслуг`, `ВозвратТоваровОтПокупателя`, `КорректировкаРеализации`.

Projection ДОЛЖЕН (SHALL) хранить как минимум три денежные меры:
- `amount_with_vat`
- `amount_without_vat`
- `vat_amount`

Projection ДОЛЖЕН (SHALL) учитывать как документы, созданные Command Center, так и ручные документы пользователя, если они влияют на фактический баланс и доступны для чтения из ИБ.

Primary sync path НЕ ДОЛЖЕН (SHALL NOT) выполнять unbounded full scan всего бухгалтерского регистра; worker sync ДОЛЖЕН (SHALL) ограничивать чтение организациями пула, кварталом и счетами/типами движений, используемыми отчётом `Продажи`.

Bounded account subset ДОЛЖЕН (SHALL) резолвиться через pinned revision canonical `GLAccountSet` и member `GLAccount` bindings, а не через hardcoded account codes в runtime defaults.

Primary production read path ДОЛЖЕН (SHALL) использовать только поддерживаемые published integration surfaces 1С: standard OData entities/functions/virtual tables или явный published HTTP service contract. Система НЕ ДОЛЖНА (SHALL NOT) использовать прямой доступ к таблицам БД ИБ как основной путь factual sync в production.

#### Scenario: Worker sync читает bounded slice через canonical GLAccountSet
- **GIVEN** для пула известны организации, квартал и pinned revision selected `GLAccountSet`, соответствующий отчёту `Продажи`
- **WHEN** `read worker` обновляет factual projection
- **THEN** он резолвит target account refs через member `GLAccount` bindings этого набора
- **AND** не использует hardcoded runtime constants как source-of-truth для bounded account scope

## ADDED Requirements

### Requirement: Factual preflight MUST fail-closed на incomplete reusable account coverage до worker execution
Система ДОЛЖНА (SHALL) до старта factual worker execution проверять coverage selected `GLAccountSet` по каждой target ИБ и возвращать machine-readable blocker, если хотя бы один required account не имеет валидного binding в target chart of accounts.

Система НЕ ДОЛЖНА (SHALL NOT) откладывать такую несовместимость до глубокой OData ошибки внутри running worker, если её можно детерминированно обнаружить в preflight/readiness path.

#### Scenario: Missing member binding блокирует factual sync до enqueue
- **GIVEN** selected `GLAccountSet` содержит canonical account, отсутствующий в binding coverage для target ИБ
- **WHEN** factual preflight или default workspace sync проверяет readiness
- **THEN** система завершает проверку fail-closed с machine-readable blocker по `gl_account`
- **AND** factual workflow execution не enqueue'ится

### Requirement: Factual runtime artifacts MUST pin `GLAccountSet` revision
Система ДОЛЖНА (SHALL) сохранять в factual preflight results, checkpoints и связанных runtime artifacts first-class machine-readable scope contract, включающий как минимум:
- версию scope contract;
- идентификатор pinned `GLAccountSet` revision;
- effective member snapshot;
- target-specific `resolved_bindings` snapshot;
- stable scope fingerprint, привязанный к effective members и quarter scope.

Система НЕ ДОЛЖНА (SHALL NOT) silently пересчитывать historical readiness или replay на latest revision profile, если runtime context уже был создан под предыдущую revision.
Система НЕ ДОЛЖНА (SHALL NOT) повторно резолвить latest target bindings для factual artifact, который уже содержит pinned `resolved_bindings`.

#### Scenario: Поздняя правка account set не меняет historical factual checkpoint scope
- **GIVEN** factual checkpoint уже создан с pinned `GLAccountSet` revision
- **WHEN** оператор публикует новую revision того же account set
- **THEN** существующий checkpoint сохраняет ранее pinned revision и effective members
- **AND** historical quarter scope не меняется автоматически только из-за новой latest revision

#### Scenario: Historical replay использует pinned target bindings, даже если current binding уже изменён
- **GIVEN** factual artifact уже содержит `resolved_bindings` snapshot для target ИБ
- **AND** после этого оператор изменил current `GLAccount` binding или target `Ref_Key`
- **WHEN** выполняется historical replay этого artifact
- **THEN** runtime использует pinned `resolved_bindings` snapshot из artifact
- **AND** не пере-резолвит latest binding state для той же target ИБ

#### Scenario: Missing pinned binding snapshot блокирует replay fail-closed
- **GIVEN** factual artifact требует execution по target ИБ, но `resolved_bindings` snapshot отсутствует или неполон
- **WHEN** runtime пытается выполнить replay
- **THEN** выполнение завершается fail-closed с machine-readable blocker
- **AND** система не подменяет отсутствующий snapshot latest binding lookup

### Requirement: Factual scope rollout MUST быть versioned, dual-read и rollback-safe
Система ДОЛЖНА (SHALL) публиковать versioned factual scope contract для bounded account subset, не меняя на bridge-периоде верхнеуровневые runtime envelopes `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1`.

Для этого change nested contract `factual_scope_contract.v2` ДОЛЖЕН (SHALL) включать как минимум:
- `gl_account_set_revision_id`;
- `effective_members`;
- `resolved_bindings`;
- `scope_fingerprint`.

На миграционном мосте система ДОЛЖНА (SHALL) выполнять dual-write:
- nested `factual_scope_contract.v2`;
- legacy compatibility fields `account_codes`, достаточные для старого worker/runtime path.

Worker и orchestrator runtime ДОЛЖНЫ (SHALL) поддерживать dual-read на период cutover: внутри текущих `v1` envelopes предпочитать nested `factual_scope_contract.v2` и его pinned `resolved_bindings`, если они доступны, и корректно обрабатывать legacy artifact, если он был выпущен до cutover или используется при rollback.

Система НЕ ДОЛЖНА (SHALL NOT) требовать rebuild historical checkpoints или recompute latest effective members только для того, чтобы пережить rollout/rollback factual scope contract.

#### Scenario: Worker предпочитает nested `factual_scope_contract.v2`, но legacy checkpoint остаётся исполнимым
- **GIVEN** новый factual checkpoint уже содержит nested `factual_scope_contract.v2` и legacy `account_codes` внутри текущего `pool_factual_sync_workflow.v1`
- **WHEN** worker читает runtime artifact после cutover
- **THEN** он использует pinned nested `factual_scope_contract.v2` как source-of-truth
- **AND** legacy fields остаются sufficient fallback для rollback-safe совместимости

#### Scenario: Rollback не требует пересборки historical factual artifacts
- **GIVEN** factual artifacts были выпущены до завершения cutover и содержат только legacy `account_codes` или transitional dual-write payload
- **WHEN** команда выполняет rollback worker/orchestrator runtime
- **THEN** historical replay и inspect остаются выполнимыми без пересборки artifacts
- **AND** runtime не пересчитывает scope из latest `GLAccountSet` revision или runtime defaults
