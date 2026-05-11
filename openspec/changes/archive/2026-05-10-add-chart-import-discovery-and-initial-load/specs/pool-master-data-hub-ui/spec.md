## ADDED Requirements

### Requirement: Chart Import UI MUST make reference database and discovered chart selection the primary setup path
Система ДОЛЖНА (SHALL) в зоне `Chart Import` показывать primary setup flow как выбор эталонной ИБ и discovered chart candidate, а не как free-text ввод `chart_identity`.

UI ДОЛЖЕН (SHALL) показывать для candidate:
- `chart_identity`;
- display name;
- compatibility markers;
- derivation/confidence;
- source evidence version/fingerprint;
- blocking diagnostics, если candidate incomplete.

#### Scenario: Оператор выбирает план счетов из обнаруженных candidates
- **GIVEN** оператор открыл `Chart Import`
- **WHEN** он выбирает reference database
- **THEN** UI загружает discovered chart candidates для этой database
- **AND** оператор выбирает candidate из списка
- **AND** free-text `chart_identity` не является основным required input
- **AND** UI показывает, из какой source evidence version получен candidate

#### Scenario: Incomplete candidate не выглядит готовым к загрузке
- **GIVEN** discovery вернул diagnostic вместо usable candidate
- **WHEN** UI показывает результат discovery
- **THEN** primary initial-load action заблокирован
- **AND** оператор видит machine-readable причину и возможный remediation path

### Requirement: Chart Import UI MUST provide guided initial load from the selected reference database
Система ДОЛЖНА (SHALL) в `Chart Import` предоставить guided initial-load action, который ведёт оператора от выбранной эталонной ИБ и chart candidate до materialize review.

UI ДОЛЖЕН (SHALL) явно разделять стадии:
- source setup;
- preflight;
- dry-run counters;
- operator review;
- materialize result.

UI НЕ ДОЛЖЕН (SHALL NOT) скрывать первичную загрузку плана счетов за generic `Sync` launcher или за legacy `Bootstrap Import`.

#### Scenario: Guided initial load требует review перед materialize
- **GIVEN** discovery candidate выбран
- **WHEN** оператор запускает initial load
- **THEN** UI показывает preflight и dry-run results
- **AND** materialize action доступен только после dry-run success и явного operator review
- **AND** stale source/discovery evidence state требует повторного dry-run вместо materialize

#### Scenario: Manual override остаётся advanced path
- **GIVEN** discovery не дал usable result
- **WHEN** оператор открывает advanced manual override
- **THEN** UI требует `chart_identity` и override reason
- **AND** показывает, что этот path будет проверен fail-closed preflight/dry-run стадиями
