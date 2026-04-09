# Change: Довести factual monitoring до полной operator drill-down coverage, operator refresh control и рабочего rollout cadence

## Почему
Archived change `2026-03-29-add-pool-factual-balance-monitoring` доставил core factual workspace, manual review queue, carry-forward backend и 2-минутный active sync, но review текущей реализации показал три оставшихся разрыва.

Во-первых, operator-facing factual workspace не показывает полный drill-down по уже существующим данным `outgoing_amount` и carry-forward lineage, поэтому бухгалтеру всё ещё приходится догадываться "сколько уже закрыто" и "куда именно перенесён остаток". Во-вторых, у обычного оператора нет явного control surface для ручного refresh/retry factual sync в контексте конкретного `pool + quarter`, а текущий shipped path сводится к implicit refresh через workspace GET или инженерным internal/debug trigger'ам. В-третьих, rollout envelope формально описывает tiers `active / warm / cold`, но runtime фактически использует только `active` и ночной reconcile для closed quarter, поэтому warm cadence остаётся contract-only.

## Что меняется
- Явно доводится operator surface factual workspace: batch/edge drill-down обязан показывать `incoming_amount`, `outgoing_amount`, `open_balance` и carry-forward context без raw JSON inspection.
- В factual workspace появляется явный operator-facing refresh/retry action для текущего `pool + quarter`, чтобы пользователю не приходилось дёргать REST/debug path вручную.
- Rollout cadence для factual sync становится first-class runtime contract: `active`, `warm` и `cold` tiers должны не только существовать в scheduling helpers, но и реально использоваться общим classifier path.
- Workspace-triggered sync, scheduler-managed sync, workflow contract и observability surface выравниваются по одному canonical activity/tier decision.
- Добавляется acceptance coverage, которая доказывает:
  - operator видит закрытую часть и carry-forward linkage в factual workspace;
  - operator может инициировать refresh/retry factual sync из shipped UI path для конкретного `pool + quarter`;
  - scheduler/runtime действительно выдают `warm` tier для подходящих non-active factual contexts;
  - active 120-second path и nightly reconcile для closed quarter не регрессируют.

## Impact
- Affected specs: `pool-factual-balance-monitoring`
- Affected code:
  - `frontend/src/pages/Pools/PoolFactualWorkspaceDetail.tsx`
  - `frontend/src/pages/Pools/__tests__/PoolFactualPage.test.tsx`
  - `orchestrator/apps/intercompany_pools/factual_*`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_v2/urls.py`
  - `go-services/worker/internal/scheduler/*`
  - factual API/runtime/worker tests
- Non-goals:
  - не менять source-of-truth factual reads или published 1C boundary;
  - не добавлять новый top-level service/runtime;
  - не перепроектировать `/pools/runs` или settlement semantics.
