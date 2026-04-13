# Change: refactor-pool-factual-verdict-first-ui

## Почему

Текущий `/pools/factual` уже даёт богатую диагностику, но как operator-facing workspace он отвечает на главный вопрос слишком поздно: пользователь не видит за первый взгляд, всё ли у пула хорошо или требуется вмешательство.

Проблемы текущего shipped UI:
- detail pane начинается с архитектурных explainers и набора независимых status cards вместо одного итогового verdict;
- aggregate денежные показатели (`incoming_amount`, `outgoing_amount`, `open_balance`) уже есть в payload, но визуально спрятаны в мелкий prose summary, а не показаны как first-class business signal;
- master pane не помогает быстро отличить проблемный pool от здорового без последовательного открытия каждого detail;
- технические diagnostics (`scope lineage`, checkpoint errors, raw codes) конкурируют с operator summary слишком рано.

В результате factual workspace хорошо подходит для расследования, но плохо подходит для быстрого ответа на вопрос: "всё хорошо или нет, и сколько суммарно завели/вывели по пулу".

## Что меняется

- Доработать `pool-factual-balance-monitoring`, чтобы `/pools/factual` использовал `verdict-first` information architecture: один общий статус, основная причина и рекомендованное следующее действие above the fold.
- Сделать aggregate движение по пулу first-class summary: явно и крупно показывать `incoming_amount`, `outgoing_amount`, `open_balance` и derived completion ratio, если входящий объём ненулевой.
- Добавить compact per-pool health summary в master pane, чтобы оператор мог быстро выбрать проблемный pool без открытия каждого detail; для этого change может ввести отдельный lightweight factual overview read model, не расширяя generic pool catalog semantics.
- Переместить `scope lineage`, per-checkpoint diagnostics, raw error codes и handoff links в secondary diagnostics section, не убирая их из продукта.
- Добавить focused unit/browser evidence, подтверждающее, что пользователь видит verdict и aggregate pool movement до diagnostic detail.

## Impact

- Affected specs:
  - `pool-factual-balance-monitoring`
- Affected code (expected, when implementing this change):
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/pages/Pools/PoolFactualWorkspacePage.tsx`
  - `frontend/src/pages/Pools/PoolFactualWorkspaceDetail.tsx`
  - `frontend/src/pages/Pools/__tests__/PoolFactualPage.test.tsx`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_v2/tests/test_pool_factual_api.py`
  - `contracts/orchestrator/**`
  - `frontend/tests/browser/**`

## Explicitly Out Of Scope

- Broad redesign factual backend payload shape, source-profile semantics, preflight/readiness logic или worker contracts.
- Расширение generic `/api/v2/pools/` contract factual-specific health полями для всех pool-domain surfaces; если master pane нужен отдельный data source, change должен использовать узкий factual overview contract.
- Локализационный rollout `/pools/factual`; copy hierarchy меняется здесь, а canonical i18n wiring покрывается отдельным change.
- Repo-wide refactor других `/pools/*` workspaces.
- Новые locales сверх уже поддерживаемых baseline.

## Assumptions

- Текущий `PoolFactualWorkspace` payload уже содержит все сигналы, нужные для UI refactor: `incoming_amount`, `outgoing_amount`, `open_balance`, freshness/backlog/review totals, checkpoint statuses и links.
- Selected-pool `verdict-first` detail может использовать текущий `PoolFactualWorkspace` payload без обязательного redesign workspace contract.
- Compact summary в master pane не должен зависеть от sequential detail fetch per pool и не должен требовать factual enrichment общего `/api/v2/pools/`; если текущих route-level данных недостаточно, change вводит отдельный factual overview contract, выровненный с quarter context workspace.
- Если `add-pool-factual-internationalization-rollout` будет реализован раньше или параллельно, новый verdict-first layout должен использовать тот copy layer, который на тот момент является baseline, без изменения UX contract этого change.
