## MODIFIED Requirements

### Requirement: Pools MUST предоставлять отдельный master-data workspace для оператора
Система ДОЛЖНА (SHALL) предоставлять отдельную страницу `/pools/master-data` как рабочее пространство для управления каноническими master-data и reusable account сущностями в tenant scope.

Система ДОЛЖНА (SHALL) поддерживать в workspace минимум следующие рабочие зоны:
- `Party`;
- `Item`;
- `Contract`;
- `TaxProfile`;
- `GLAccount`;
- `GLAccountSet`;
- `Bindings`;
- `Chart Import`;
- `Sync`;
- `Bootstrap Import`.

Workspace ДОЛЖЕН (SHALL) быть доступен из основного меню Pools, работать в рамках текущего tenant context и расширяться внутри canonical platform shell, а не через второй parallel page foundation.

#### Scenario: Оператор открывает chart import zone внутри master-data workspace
- **GIVEN** пользователь имеет доступ к Pools и выбран tenant context
- **WHEN** пользователь открывает `/pools/master-data`
- **THEN** система показывает рабочую зону `Chart Import` вместе с остальными master-data зонами
- **AND** оператор остаётся внутри canonical workspace shell без второго route-level foundation

### Requirement: Workspace MUST показывать capability-gated sync и revision states для reusable accounts
Система ДОЛЖНА (SHALL) явно показывать оператору shipped capability state reusable accounts:
- `GLAccount` как chart-import/bootstrap-capable entity без generic mutating outbound/bidirectional sync actions;
- `GLAccountSet` как profile с draft/publish/revision lifecycle и non-actionable sync state.

#### Scenario: UI не подменяет canonical chart import generic sync semantics
- **GIVEN** оператор работает с reusable account surfaces в `/pools/master-data`
- **WHEN** система показывает доступные lifecycle actions для `GLAccount`
- **THEN** UI разделяет `Chart Import` и `Bootstrap Import` от generic `Sync`
- **AND** оператор не получает ложный сигнал, будто полный canonical chart-of-accounts нужно заводить через mutating sync launcher

## ADDED Requirements

### Requirement: Chart Import zone MUST предоставлять authoritative-source materialization lifecycle
Система ДОЛЖНА (SHALL) в `/pools/master-data` предоставлять отдельную зону `Chart Import` для canonical chart-of-accounts materialization.

Зона ДОЛЖНА (SHALL) поддерживать как минимум:
- inspect authoritative source по compatibility class;
- `preflight`;
- `dry-run`;
- `materialize`;
- `verify followers` и/или `backfill bindings`.

Система НЕ ДОЛЖНА (SHALL NOT) прятать этот lifecycle внутри generic `Sync` drawer или внутри `GLAccountSet` profile editor.

#### Scenario: Оператор проходит staged lifecycle chart materialization
- **GIVEN** для compatibility class настроен authoritative source
- **WHEN** оператор открывает `Chart Import`
- **THEN** UI показывает staged lifecycle `preflight -> dry-run -> materialize -> verify/backfill`
- **AND** summary/results читаются как отдельный operator-facing chart workflow, а не как sync launch history

### Requirement: Chart Import diagnostics MUST вести в Bindings remediation для follower failures
Система ДОЛЖНА (SHALL) при fail-closed follower verify/backfill показывать machine-readable diagnostics и handoff в `Bindings` workspace.

Handoff ДОЛЖЕН (SHALL) сохранять database-scoped remediation context как минимум для:
- `entityType=gl_account`;
- `databaseId=<target database>`;
- при наличии `canonicalId=<canonical account>`.

#### Scenario: Follower verify failure ведёт оператора в chart-scoped bindings remediation
- **GIVEN** `Chart Import` verify/backfill завершился ambiguity, stale или missing-binding failure для follower database
- **WHEN** оператор открывает detail проблемного follower outcome
- **THEN** UI показывает operator-facing причину блокировки
- **AND** предоставляет deep-link в `Bindings` workspace с сохранённым database/entity remediation context
