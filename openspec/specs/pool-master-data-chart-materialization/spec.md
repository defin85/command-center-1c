# pool-master-data-chart-materialization Specification

## Purpose
TBD - created by archiving change add-pool-master-data-chart-materialization-path. Update Purpose after archive.
## Requirements
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

### Requirement: Chart Import MUST discover row-source readiness for OData ChartOfAccounts candidates
Система ДОЛЖНА (SHALL) при Chart Import discovery различать discovery `chart_identity` и readiness источника строк, из которого `dry-run/materialize` сможет прочитать полный список счетов выбранного плана счетов.

Discovery candidate ДОЛЖЕН (SHALL) включать row-source readiness metadata минимум:
- `row_source_status` (`ready`, `needs_probe`, `needs_mapping`, `unavailable`);
- `row_source_kind`;
- `row_source_entity_name`;
- `row_source_field_mapping`;
- `row_source_select_fields`;
- `row_source_evidence_fingerprint`;
- machine-readable diagnostics.

Если candidate найден только по metadata catalog field/type information, система ДОЛЖНА (SHALL) показывать `chart_identity`, но НЕ ДОЛЖНА (SHALL NOT) считать candidate готовым к primary initial load без подтверждённого row source.

Discovery/preflight НЕ ДОЛЖНЫ (SHALL NOT) читать полный chart row set. Они МОГУТ (MAY) выполнить bounded OData probe для проверки endpoint/auth/entity/required fields.

Discovery ДОЛЖЕН (SHALL) оставаться read-only для Command Center state: он НЕ ДОЛЖЕН (SHALL NOT) создавать authoritative chart source, изменять `Database.metadata`, сохранять global bootstrap mapping или запускать lifecycle jobs.

Discovery response, diagnostics и row-source evidence НЕ ДОЛЖНЫ (SHALL NOT) содержать OData passwords, authorization headers, raw Basic auth material или raw chart row payload.

#### Scenario: OData ChartOfAccounts entity даёт load-ready candidate
- **GIVEN** выбранная reference database имеет OData entity `ChartOfAccounts_Хозрасчетный`
- **AND** entity доступен через tenant-bound OData credentials
- **WHEN** оператор запускает Chart Import discovery
- **THEN** система возвращает candidate с `chart_identity=ChartOfAccounts_Хозрасчетный`
- **AND** `row_source_status=ready`
- **AND** candidate содержит mapping `Ref_Key`, `Code`, `Description` для чтения строк плана счетов
- **AND** candidate содержит row-source evidence fingerprint
- **AND** discovery не создаёт authoritative chart source и не изменяет metadata выбранной database

#### Scenario: Metadata-only candidate не готов к initial load
- **GIVEN** metadata catalog snapshot содержит поле типа `StandardODATA.ChartOfAccounts_Хозрасчетный`
- **AND** система не может подтвердить readable OData row source для `ChartOfAccounts_Хозрасчетный`
- **WHEN** оператор запускает Chart Import discovery
- **THEN** система возвращает identity candidate
- **AND** `row_source_status` равен `needs_probe`, `needs_mapping` или `unavailable`
- **AND** primary initial load остаётся заблокированным до подтверждения row source

### Requirement: Chart Import initial load MUST persist selected row-source provenance
Система ДОЛЖНА (SHALL) сохранять выбранный row source для authoritative chart source как chart-scoped provenance, используемый последующими стадиями `preflight`, `dry-run` и `materialize`.

Row-source provenance ДОЛЖЕН (SHALL) включать:
- selected database id;
- OData entity name;
- field mapping;
- select fields;
- row-source derivation method;
- probe/evidence fingerprint;
- operator-reviewed diagnostics when applicable.

Row-source provenance НЕ ДОЛЖЕН (SHALL NOT) включать OData credentials, authorization headers, raw Basic auth material или raw chart row payload.

Система НЕ ДОЛЖНА (SHALL NOT) silently перезаписывать global `Database.metadata.bootstrap_import_source` при выборе Chart Import candidate.

Если система переиспользует existing global `Database.metadata.bootstrap_import_source.entities.gl_account`, она ДОЛЖНА (SHALL) сначала проверить compatibility с selected candidate и сохранить snapshot выбранного mapping в chart source metadata. Runtime НЕ ДОЛЖЕН (SHALL NOT) silently использовать изменившийся global mapping после successful dry-run.

Source revision/evidence ДОЛЖЕН (SHALL) включать row-source provenance. Если row-source entity, field mapping, selected database, metadata/probe fingerprint или credentials strategy меняются после successful dry-run, `materialize` ДОЛЖЕН (SHALL) требовать новый `preflight` и `dry-run`.

#### Scenario: Source upsert сохраняет chart-scoped row source
- **GIVEN** оператор выбрал load-ready discovery candidate
- **WHEN** система создаёт или обновляет authoritative chart source
- **THEN** chart source metadata содержит выбранный row-source provenance
- **AND** global database bootstrap mapping не меняется без отдельного явного operator action
- **AND** source revision token включает row-source evidence
- **AND** metadata не содержит credentials или raw chart rows

#### Scenario: Stale row-source evidence блокирует materialize
- **GIVEN** оператор выполнил dry-run для выбранного chart source
- **AND** row-source mapping или row-source evidence изменились после dry-run
- **WHEN** оператор пытается выполнить materialize по старому dry-run
- **THEN** система отклоняет materialize fail-closed
- **AND** требует повторить preflight и dry-run

### Requirement: Chart Import row loading MUST use ChartOfAccounts OData mapping for full initial load
Система ДОЛЖНА (SHALL) для load-ready OData candidate читать полный список счетов через chart materialization row loading path, используя выбранный chart-scoped row source.

Для standard OData entity `ChartOfAccounts_*` система ДОЛЖНА (SHALL) уметь сформировать normalized `GLAccount` rows:
- `source_ref` и/или `canonical_id` из `Ref_Key`;
- `code` из `Code`;
- `name` из `Description`;
- `chart_identity` из entity name.

Если required fields недоступны или mapping incomplete, `preflight`/`dry-run` ДОЛЖНЫ (SHALL) завершаться fail-closed с remediation-ready diagnostic.

Full row loading ДОЛЖЕН (SHALL) использовать bounded page size и deterministic output fingerprint. При `$skip/$top` pagination implementation ДОЛЖЕН (SHALL) использовать stable ordering by source key/code when supported by the OData source, либо показать snapshot-consistency diagnostic, что source rows не должны меняться во время fetch.

#### Scenario: Dry-run читает полный список счетов из выбранной ИБ
- **GIVEN** authoritative chart source содержит row-source provenance для `ChartOfAccounts_Хозрасчетный`
- **WHEN** оператор запускает dry-run
- **THEN** система постранично читает строки из OData entity `ChartOfAccounts_Хозрасчетный`
- **AND** normalized rows получают `chart_identity=ChartOfAccounts_Хозрасчетный`
- **AND** dry-run counters отражают полный список счетов, а не только metadata snapshot
- **AND** snapshot fingerprint is deterministic for identical source rows

#### Scenario: Incomplete mapping fail-closed блокирует dry-run
- **GIVEN** row-source candidate не имеет readable `Code` или display-name mapping
- **WHEN** оператор запускает preflight или dry-run
- **THEN** система возвращает machine-readable row-source diagnostic
- **AND** materialize остаётся недоступен

### Requirement: Chart Import source setup MUST discover chart identities from a selected database
Система ДОЛЖНА (SHALL) предоставлять read-only discovery path, который для выбранной database возвращает доступные chart-of-accounts candidates с stable `chart_identity`.

Discovery result ДОЛЖЕН (SHALL) включать как минимум:
- `chart_identity`;
- operator-facing `name` или fallback display label;
- `config_name`;
- `config_version`;
- `source_database_id`;
- `source_kind`;
- `derivation_method`;
- `confidence`;
- `metadata_hash`/`catalog_version` или equivalent source evidence fingerprint;
- machine-readable diagnostics.

Система НЕ ДОЛЖНА (SHALL NOT) требовать free-text `chart_identity` как основной штатный путь, если discovery может доказательно вернуть compatible chart candidate.

Discovery path ДОЛЖЕН (SHALL) быть bounded by tenant access и НЕ ДОЛЖЕН (SHALL NOT) использовать полный chart row scan как обязательный primary discovery mechanism.

#### Scenario: Discovery находит план счетов в выбранной ИБ
- **GIVEN** database имеет bootstrap/OData/metadata configuration, из которой можно вывести `ChartOfAccounts_*`
- **WHEN** оператор запускает chart discovery для этой database
- **THEN** система возвращает chart candidate со stable `chart_identity`
- **AND** candidate содержит compatibility markers `config_name` и `config_version`
- **AND** candidate указывает, каким методом identity был получен
- **AND** candidate содержит evidence fingerprint, позволяющий обнаружить stale source decision

#### Scenario: Discovery не фабрикует identity при неполных данных
- **GIVEN** database не содержит typed chart source metadata и rows не содержат `chart_identity`
- **WHEN** оператор запускает chart discovery
- **THEN** система возвращает fail-closed diagnostic
- **AND** не создаёт authoritative chart source с guessed или пустым `chart_identity`

#### Scenario: Discovery не раскрывает данные чужого tenant
- **GIVEN** database принадлежит другому tenant
- **WHEN** оператор запускает chart discovery для этой database
- **THEN** система отклоняет запрос fail-closed
- **AND** не возвращает chart candidates или metadata diagnostics этой database

### Requirement: Chart Import MUST support initial canonical load from an operator-selected reference database
Система ДОЛЖНА (SHALL) поддерживать первичную загрузку canonical chart-of-accounts из эталонной ИБ, выбранной оператором.

Initial load ДОЛЖЕН (SHALL) использовать существующий chart materialization lifecycle:
- create/update authoritative source from selected reference database and chart candidate;
- `preflight`;
- `dry-run`;
- explicit operator review;
- `materialize`.

Initial load НЕ ДОЛЖЕН (SHALL NOT) запускать generic `Sync` или legacy `Bootstrap Import` вместо chart materialization path.

Materialize stage ДОЛЖЕН (SHALL) быть привязан к current source revision/evidence и successful dry-run review. Если source или discovery evidence изменились после dry-run, system ДОЛЖНА (SHALL) требовать новый preflight/dry-run перед materialize.

#### Scenario: Оператор выполняет первичную загрузку из эталонной ИБ
- **GIVEN** оператор выбрал reference database
- **AND** discovery вернул compatible chart candidate
- **WHEN** оператор запускает initial load
- **THEN** система создаёт или обновляет authoritative chart source для выбранного candidate
- **AND** выполняет preflight и dry-run перед materialize
- **AND** materialize разрешается только после явного review dry-run counters

#### Scenario: Stale dry-run не разрешает materialize после смены source evidence
- **GIVEN** оператор выполнил dry-run для выбранного chart candidate
- **AND** authoritative source или discovery evidence изменились после dry-run
- **WHEN** оператор пытается выполнить materialize
- **THEN** система отклоняет materialize fail-closed
- **AND** требует повторить preflight и dry-run для текущего source evidence

#### Scenario: Initial load остаётся отдельным от generic sync
- **GIVEN** оператор запускает первичную загрузку плана счетов
- **WHEN** backend создаёт lifecycle jobs
- **THEN** jobs относятся к chart materialization lifecycle
- **AND** `pool-master-data-sync` launch не создаётся

### Requirement: Manual chart identity override MUST be advanced, audited, and validated against source rows
Система ДОЛЖНА (SHALL) трактовать ручной ввод `chart_identity` как advanced override, допустимый только когда discovery не может вернуть нужный candidate или оператор явно исправляет source metadata.

Manual override ДОЛЖЕН (SHALL) сохранять audit/provenance metadata:
- override reason;
- actor;
- timestamp;
- discovery diagnostics, на фоне которых был выбран override.

Preflight/dry-run ДОЛЖНЫ (SHALL) fail-closed отклонить override, если source rows не подтверждают выбранный `chart_identity`.

Если source entity configuration itself identifies `ChartOfAccounts_*`, система ДОЛЖНА (SHALL) уметь использовать это как row-level `chart_identity` provenance instead of requiring a redundant source column in every account row.

#### Scenario: Manual override сохраняет provenance
- **GIVEN** discovery не вернул usable candidate
- **WHEN** оператор вручную вводит `chart_identity` через advanced override
- **THEN** система требует reason
- **AND** сохраняет override provenance в chart source metadata
- **AND** дальнейшие lifecycle stages валидируют identity against source rows

#### Scenario: Неверный override блокируется на dry-run
- **GIVEN** operator вручную указал `chart_identity`
- **AND** source rows не содержат matching chart scope
- **WHEN** система выполняет dry-run
- **THEN** dry-run завершается fail-closed diagnostic
- **AND** materialize остаётся недоступен

#### Scenario: Source entity identity stamps GLAccount rows
- **GIVEN** bootstrap source config maps `gl_account` to OData entity `ChartOfAccounts_Хозрасчетный`
- **AND** source rows contain account code/name but no redundant `chart_identity` column
- **WHEN** система выполняет dry-run для matching discovered candidate
- **THEN** normalized rows receive `chart_identity=ChartOfAccounts_Хозрасчетный` from source config provenance
- **AND** dry-run does not fail only because the row lacks a duplicate chart identity field
