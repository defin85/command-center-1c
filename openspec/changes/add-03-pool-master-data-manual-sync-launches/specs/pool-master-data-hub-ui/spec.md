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
- `Sync`;
- `Bootstrap Import`.

Workspace ДОЛЖЕН (SHALL) быть доступен из основного меню Pools, работать в рамках текущего tenant context и расширяться внутри canonical platform shell, а не через второй parallel page foundation.

#### Scenario: Оператор открывает sync zone внутри master-data workspace
- **GIVEN** пользователь имеет доступ к Pools и выбран tenant context
- **WHEN** пользователь открывает `/pools/master-data`
- **THEN** система показывает рабочую зону `Sync` вместе с остальными master-data зонами
- **AND** оператор остаётся внутри canonical workspace shell без второго route-level foundation

## ADDED Requirements

### Requirement: Sync zone MUST предоставлять manual launch drawer для cluster-wide и database-scoped sync
Система ДОЛЖНА (SHALL) в зоне `Sync` предоставлять operator action `Launch Sync`, который открывает launcher drawer или другой canonical authoring shell.

Launcher ДОЛЖЕН (SHALL) поддерживать поля:
- `mode`: `inbound|outbound|reconcile`;
- `target_mode`: `cluster_all|database_set`;
- выбор кластера для `cluster_all`;
- выбор конкретных ИБ для `database_set`;
- `entity_scope` из registry-driven sync-capable entity types.

Launcher НЕ ДОЛЖЕН (SHALL NOT) показывать generic mutating launch options для entity types без соответствующих sync capabilities.

#### Scenario: Оператор запускает сбор по всем ИБ кластера
- **GIVEN** оператор открыл `/pools/master-data?tab=sync`
- **WHEN** он выбирает `mode=inbound`, `target_mode=cluster_all`, конкретный кластер и entity scope
- **THEN** UI отправляет canonical launch request в namespace `/api/v2/pools/master-data/`
- **AND** после успешного ответа показывает созданный launch request в operator-facing history

#### Scenario: Оператор запускает sync по явному набору ИБ
- **GIVEN** оператор открыл `Sync` zone
- **WHEN** он выбирает `target_mode=database_set`, несколько конкретных ИБ и entity scope
- **THEN** UI отправляет launch request только для выбранных ИБ
- **AND** оператор получает launch detail с immutable snapshot выбранных databases

#### Scenario: Unsupported entity type не появляется в launch entity scope
- **GIVEN** generated registry не публикует sync capability для `gl_account_set`
- **WHEN** UI строит `entity_scope` options для launcher drawer
- **THEN** `GLAccountSet` не появляется в selectable launch entities
- **AND** система не создаёт illusion generic mutating sync support

### Requirement: Sync zone MUST показывать launch history, aggregate progress и per-scope detail
Система ДОЛЖНА (SHALL) в `Sync` зоне показывать operator-facing history ручных launch requests.

History/detail ДОЛЖНЫ (SHALL) включать как минимум:
- `created_at`, `requested_by`, `mode`, `target_mode`;
- target summary (`cluster` или count selected databases);
- aggregate counters `scheduled/coalesced/skipped/failed/completed`;
- per-scope detail по `(database, entity)` с outcome и ссылкой на child sync job, если он создан или переиспользован.

UI ДОЛЖЕН (SHALL) поддерживать deep-link или handoff в существующий `Sync Status`/`Conflict Queue` для remediation проблемного scope.

#### Scenario: Оператор открывает launch detail и переходит к проблемному scope
- **GIVEN** manual launch завершился смешанным результатом
- **WHEN** оператор открывает detail конкретного launch request
- **THEN** UI показывает aggregate counters и список child scope с outcome
- **AND** оператор может перейти к отфильтрованному `Sync Status` или `Conflict Queue` для выбранного `(database, entity)`

### Requirement: Launcher UI MUST сохранять operator input и fail-closed diagnostics при create errors
Система ДОЛЖНА (SHALL) сохранять выбранные `mode`, `target_mode`, cluster/database selection и `entity_scope`, если create launch request завершился Problem Details ошибкой.

Система НЕ ДОЛЖНА (SHALL NOT) очищать operator input после validation/permission failure.

#### Scenario: Ошибка create launch не сбрасывает уже выбранный scope
- **GIVEN** оператор заполнил launcher drawer
- **WHEN** API отклоняет create request из-за validation или access error
- **THEN** UI показывает operator-facing machine-readable ошибку
- **AND** ранее выбранные targets и entity scope остаются в форме для повторной попытки
