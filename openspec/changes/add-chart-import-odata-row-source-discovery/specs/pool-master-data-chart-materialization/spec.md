## ADDED Requirements

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
