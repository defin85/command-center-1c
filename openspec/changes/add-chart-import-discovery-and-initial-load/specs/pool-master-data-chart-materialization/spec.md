## ADDED Requirements

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
