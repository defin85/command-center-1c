## ADDED Requirements

### Requirement: Canonical chart materialization MUST use one authoritative source per compatibility class
Система ДОЛЖНА (SHALL) materialize-ить полный canonical chart-of-accounts из одной authoritative source database, выбранной для compatibility class `(tenant, chart_identity, config_name, config_version)`.

Система НЕ ДОЛЖНА (SHALL NOT) silently merge-ить несколько source databases одного chart в один canonical chart без явного operator decision.

Canonical `GLAccount` identity ДОЛЖНА (SHALL) вычисляться детерминированно как минимум из normalized `chart_identity` и account `code`; source `Ref_Key` НЕ ДОЛЖЕН (SHALL NOT) становиться canonical identity.

#### Scenario: Оператор materialize-ит canonical chart из authoritative source
- **GIVEN** для compatibility class выбран authoritative source database
- **WHEN** система выполняет canonical chart materialization
- **THEN** полный snapshot счетов читается из этой source database
- **AND** resulting canonical `GLAccount` records materialize-ятся в master-data hub без превращения source `Ref_Key` в canonical key

#### Scenario: Второй source той же compatibility class не merge-ится silently
- **GIVEN** в tenant существуют две databases с тем же `chart_identity`, `config_name` и `config_version`
- **WHEN** authoritative source уже выбран и оператор запускает materialization
- **THEN** система использует только выбранный authoritative source
- **AND** другая database не считается равноправным merge source без отдельного operator action

### Requirement: Chart materialization lifecycle MUST be snapshot-first and staged
Система ДОЛЖНА (SHALL) выполнять canonical chart materialization как staged lifecycle:
- `preflight`
- `dry-run`
- `materialize`
- `verify_followers` и/или `backfill_bindings`

Система НЕ ДОЛЖНА (SHALL NOT) выполнять materialization как generic mutating sync launch в existing `Sync` runtime surface.

#### Scenario: Dry-run обязателен перед materialize
- **GIVEN** authoritative source настроен
- **WHEN** оператор хочет materialize-ить canonical chart
- **THEN** система сначала даёт preflight и dry-run summary
- **AND** execute materialization не считается разрешённым, пока staged checks не прошли fail-closed

#### Scenario: Chart import не подменяется generic sync launcher
- **GIVEN** оператор работает с полным canonical chart-of-accounts
- **WHEN** он запускает materialization workflow
- **THEN** система использует отдельный chart materialization path
- **AND** не интерпретирует его как inbound/outbound/reconcile sync launch

### Requirement: Follower verification MUST materialize target-local GLAccount bindings by code and chart scope
Система ДОЛЖНА (SHALL) после canonical materialization уметь verify/backfill `GLAccount` bindings для follower databases по `(database_id, chart_identity, code)`.

Система ДОЛЖНА (SHALL) сохранять target-local `Ref_Key` только как binding конкретной follower database, а не как canonical state.

При ambiguity, missing code match или stale `Ref_Key` verify/backfill path ДОЛЖЕН (SHALL) завершаться fail-closed с machine-readable diagnostics.

#### Scenario: Follower database получает chart-scoped GLAccount bindings
- **GIVEN** canonical chart уже materialize-ен из authoritative source
- **AND** follower database содержит тот же chart of accounts
- **WHEN** система выполняет `backfill_bindings`
- **THEN** она materialize-ит или обновляет `GLAccount` bindings по `code + chart_identity`
- **AND** resulting bindings остаются target-local layer для follower database

#### Scenario: Ambiguous follower coverage блокирует auto-backfill
- **GIVEN** в follower database account code резолвится неоднозначно или противоречит ожидаемому chart scope
- **WHEN** система выполняет follower verify/backfill
- **THEN** операция завершается fail-closed с machine-readable ambiguity/stale diagnostic
- **AND** binding не materialize-ится silently

### Requirement: Canonical chart lifecycle MUST preserve provenance and safe retirement
Система ДОЛЖНА (SHALL) сохранять provenance каждого materialization snapshot, включая как минимум:
- authoritative source database;
- snapshot hash или эквивалентный stable fingerprint;
- row counters и timestamps.

Если очередной authoritative snapshot больше не содержит ранее canonical account, система НЕ ДОЛЖНА (SHALL NOT) hard-delete-ить его silently по умолчанию.

Вместо этого canonical chart lifecycle ДОЛЖЕН (SHALL) использовать retirement/provenance-preserving semantics, совместимые с historical `GLAccountSet` revisions и downstream runtime lineage.

#### Scenario: Snapshot provenance остаётся доступным для operator inspection
- **GIVEN** materialization job успешно завершён
- **WHEN** оператор открывает его detail
- **THEN** система показывает source database, snapshot fingerprint и counters
- **AND** operator может понять, из какого authoritative chart был получен canonical result

#### Scenario: Account исчезает из source snapshot без silent hard delete
- **GIVEN** ранее materialize-ённый canonical account отсутствует в новом authoritative snapshot
- **WHEN** система применяет новый snapshot
- **THEN** account получает retirement/provenance-preserving state
- **AND** historical `GLAccountSet` revisions не теряют свой lineage только из-за silent hard delete
