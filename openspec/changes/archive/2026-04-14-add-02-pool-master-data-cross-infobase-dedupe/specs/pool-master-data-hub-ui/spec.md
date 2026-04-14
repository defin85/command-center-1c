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
- `Bootstrap Import`;
- `Dedupe Review`.

Workspace ДОЛЖЕН (SHALL) быть доступен из основного меню Pools, работать в рамках текущего tenant context и расширяться внутри canonical platform shell, а не через второй parallel page foundation.

#### Scenario: Оператор открывает `Dedupe Review` внутри master-data workspace
- **GIVEN** пользователь имеет доступ к Pools и выбран tenant context
- **WHEN** пользователь открывает `/pools/master-data` и переключается в `Dedupe Review`
- **THEN** система показывает dedupe-oriented зону внутри того же workspace shell
- **AND** review flow остаётся tenant-scoped и не уходит в отдельный parallel route foundation

## ADDED Requirements

### Requirement: Workspace MUST показывать dedupe review queue, history и provenance detail
Система ДОЛЖНА (SHALL) в `/pools/master-data` предоставлять operator-facing `Dedupe Review` surface для cross-infobase source-of-truth resolution.

Surface ДОЛЖЕН (SHALL) показывать как минимум:
- queue unresolved items;
- recent auto/manual resolution history;
- filters по `entity_type`, status, reason code, cluster/database scope;
- detail по выбранному review item.

Detail ДОЛЖЕН (SHALL) включать как минимум:
- candidate cluster summary;
- proposed canonical survivor/result, если он существует;
- source provenance по всем включённым source records;
- normalized match signals;
- conflicting fields;
- affected bindings или rollout/publication blockers, если они есть.

#### Scenario: Оператор видит, почему cluster попал в review-required состояние
- **GIVEN** cross-infobase dedupe создал unresolved item для `Party`
- **WHEN** оператор открывает detail этого item в `Dedupe Review`
- **THEN** UI показывает source records из разных ИБ, match signals и conflicting fields
- **AND** оператору не нужно читать raw JSON или backend logs, чтобы понять причину блокировки

### Requirement: UI MUST предоставлять explicit resolution actions и handoff из blocked rollout surfaces
Система ДОЛЖНА (SHALL) предоставлять в `Dedupe Review` explicit operator actions как минимум:
- `accept merge`;
- `choose survivor`;
- `mark distinct`.

Система ДОЛЖНА (SHALL) сохранять URL-addressable review context, чтобы blocked collection/sync/publication surfaces могли делать deep-link в конкретный review item.

Система НЕ ДОЛЖНА (SHALL NOT) скрывать unresolved dedupe blocker behind generic error toast без перехода к actionable review surface.

#### Scenario: Blocked rollout ведёт оператора в конкретный review item
- **GIVEN** manual rollout или publication заблокирован unresolved dedupe cluster
- **WHEN** оператор открывает blocker из соответствующего surface
- **THEN** UI делает deep-link в `Dedupe Review` на конкретный item
- **AND** оператор может сразу принять merge, выбрать survivor или пометить записи как distinct

#### Scenario: Manual resolution сохраняет review context после API round-trip
- **GIVEN** оператор открыл review item и запускает `choose survivor`
- **WHEN** backend подтверждает изменение resolution state
- **THEN** UI обновляет статус и history без потери выбранного review context
- **AND** дальнейший retry rollout/publication может использовать уже resolved canonical state
