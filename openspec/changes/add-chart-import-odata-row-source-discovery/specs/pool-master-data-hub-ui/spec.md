## ADDED Requirements

### Requirement: Chart Import UI MUST distinguish identity discovery from row-source readiness
Система ДОЛЖНА (SHALL) в `Chart Import` показывать оператору отдельно:
- обнаруженный `chart_identity`;
- readiness источника строк для initial load;
- row-source mapping/probe evidence.

UI НЕ ДОЛЖЕН (SHALL NOT) показывать metadata-only candidate как готовый к полной загрузке плана счетов.

UI НЕ ДОЛЖЕН (SHALL NOT) показывать raw credentials, authorization headers или raw chart row payload из probe/provenance/diagnostics.

#### Scenario: Load-ready candidate показывает row-source evidence
- **GIVEN** discovery вернул candidate с `row_source_status=ready`
- **WHEN** UI показывает candidate
- **THEN** оператор видит OData entity, key/code/name mapping и evidence fingerprint
- **AND** `Prepare Initial Load` доступен после выбора candidate
- **AND** UI не показывает secrets или raw chart rows

#### Scenario: Identity-only candidate блокирует initial load
- **GIVEN** discovery вернул candidate с `chart_identity`, но без готового row source
- **WHEN** оператор выбирает candidate
- **THEN** UI показывает, что metadata snapshot не содержит строки плана счетов
- **AND** `Prepare Initial Load` disabled
- **AND** UI показывает remediation path: probe OData, configure mapping, or use advanced override with explicit row source

### Requirement: Chart Import UI MUST require reviewed row-source mapping before initial load
Система ДОЛЖНА (SHALL) перед `Prepare Initial Load` показывать operator-reviewed row-source mapping для selected candidate.

Для standard `ChartOfAccounts_*` mapping UI МОЖЕТ (MAY) auto-populate deterministic fields, но ДОЛЖЕН (SHALL) показывать их до запуска `preflight/dry-run`.

Manual `chart_identity` override НЕ ДОЛЖЕН (SHALL NOT) обходить row-source readiness gate.

#### Scenario: Оператор подтверждает auto-discovered OData mapping
- **GIVEN** selected candidate load-ready
- **WHEN** оператор готовит initial load
- **THEN** UI показывает mapping `Ref_Key`, `Code`, `Description`
- **AND** source setup сохраняет row-source provenance вместе с chart candidate
- **AND** дальнейший materialize использует тот же reviewed source evidence

#### Scenario: Manual override требует row-source mapping
- **GIVEN** оператор включил advanced manual override
- **WHEN** он вводит `chart_identity`
- **THEN** UI всё равно требует готовый row source или explicit mapping/probe
- **AND** initial load не стартует только на основании free-text `chart_identity`
