## MODIFIED Requirements

### Requirement: Monitoring MUST предоставлять near-real-time summary и drill-down по factual balance

Система ДОЛЖНА (SHALL) предоставлять операторский summary/drill-down по factual balance, достаточный для ответа на вопросы:

- сколько вошло в пул;
- сколько прошло по каждому ребру;
- где сумма застряла;
- сколько уже закрыто фактическими реализациями;
- какой остаток переносится в следующий квартал.

Operator-facing factual workspace ДОЛЖЕН (SHALL) показывать эти ответы через primary UI surface, а не требовать raw JSON inspection или ручного сопоставления backend payload.

Для этого batch settlement и edge drill-down ДОЛЖНЫ (SHALL) как минимум отображать:
- `incoming_amount`;
- `outgoing_amount`;
- `open_balance`;
- carry-forward context для batch/status `carried_forward`, включая target quarter и source/target linkage, достаточные для операторского анализа.

Для reachable ИБ система ДОЛЖНА (SHALL) стремиться поддерживать freshness projection не хуже 2 минут. При недоступности ИБ, maintenance window или блокировке внешних сеансов система ДОЛЖНА (SHALL) показывать staleness/freshness metadata вместо silent freeze.

#### Scenario: Бухгалтер видит закрытую часть и carry-forward без raw JSON inspection
- **GIVEN** batch частично закрыт или переведён в `carried_forward`
- **WHEN** бухгалтер открывает centralized factual dashboard
- **THEN** factual workspace показывает `incoming_amount`, `outgoing_amount` и `open_balance` на operator-facing batch/edge drill-down
- **AND** при carry-forward оператор видит target quarter и linkage на source/target factual context
- **AND** ему не нужно читать raw metadata JSON, чтобы понять сколько уже закрыто и куда перенесён остаток

#### Scenario: Бухгалтер видит, где сумма застряла, без открытия каждой ИБ
- **GIVEN** несколько узлов и рёбер пула имеют ненулевой `open_balance`
- **WHEN** бухгалтер открывает centralized balance dashboard
- **THEN** summary показывает проблемные pool/org/edge с их остатками
- **AND** drill-down раскрывает batch и квартальный контекст без перехода в каждую ИБ вручную

## ADDED Requirements

### Requirement: Factual workspace MUST давать operator-facing refresh/retry path для текущего pool и quarter

Система ДОЛЖНА (SHALL) предоставлять в shipped factual workspace явное operator-facing действие для refresh/retry factual sync в контексте конкретного `pool + quarter`.

Этот path ДОЛЖЕН (SHALL):
- работать из standard operator surface без ручного `curl`, `eval-django` или internal-service endpoint knowledge;
- reuse'ить существующий bounded factual sync contract внутри текущих runtime boundaries;
- показывать пользователю machine-readable progress/result state для pending, running, success и failure;
- respect'ить existing checkpoint/idempotency/freshness guardrails, а не enqueue'ить бесконтрольные дубликаты.

Система НЕ ДОЛЖНА (SHALL NOT) считать debug/runbook commands primary operator path для ручного обновления factual сверки.

#### Scenario: Оператор вручную обновляет factual сверку из workspace
- **GIVEN** оператор видит stale factual summary или хочет ускорить refresh для конкретного `pool + quarter`
- **WHEN** он использует shipped refresh/retry control в factual workspace
- **THEN** система запускает bounded factual sync для этого context внутри существующих runtime boundaries
- **AND** UI показывает pending/running/result state без требования ручного REST/debug вызова
- **AND** повторные нажатия не создают бесконтрольные дубликаты, если checkpoint уже находится в `pending` или `running`

### Requirement: Factual rollout cadence MUST активировать declared polling tiers через canonical activity classification

Система ДОЛЖНА (SHALL) использовать declared polling tiers `active`, `warm` и `cold` как реальный runtime contract factual sync, а не только как helper/config definitions.

Для этого система ДОЛЖНА (SHALL):
- принимать canonical activity decision на orchestrator path для factual sync context;
- проводить выбранный tier в workflow contract, checkpoint metadata и observability-facing surfaces;
- использовать `active` cadence для operator-driven/current-quarter factual contexts;
- использовать `warm` cadence для non-active, но ещё operationally relevant open factual contexts;
- использовать `cold` cadence для low-activity contexts, не подменяя им отдельный nightly reconcile path для closed quarter.

Система НЕ ДОЛЖНА (SHALL NOT) держать `warm` tier только в helper constants или unit tests без фактического runtime wiring.

#### Scenario: Scheduler выдаёт warm tier для non-active открытого factual context
- **GIVEN** factual quarter больше не считается active operator context, но по нему остаются открытые settlement или operationally relevant balances
- **WHEN** scheduler-managed factual sync выбирает cadence для этого context
- **THEN** workflow contract и checkpoint metadata получают `polling_tier=warm`
- **AND** effective poll interval соответствует warm cadence
- **AND** runtime не маскирует этот path под `active`

#### Scenario: Workspace request сохраняет active cadence без регрессии nightly reconcile
- **GIVEN** оператор открывает factual workspace для актуального quarter context
- **WHEN** route-triggered default sync или operator-triggered refresh запускает readiness/execution path
- **THEN** factual sync остаётся на `active` cadence с target freshness 2 минуты
- **AND** отдельный closed-quarter reconcile job продолжает существовать независимо от этого path
