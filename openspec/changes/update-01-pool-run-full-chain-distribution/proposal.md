# Change: Гарантировать полное распределение суммы по цепочке организаций в pool run

## Why
Сейчас runtime путь `pool run` не гарантирует, что исходная сумма реально распределена по активному графу пула.

Code-first evidence:
- Runtime шаги `pool.distribution_calculation.*` в текущем `PoolDomain` формируют только summary (`starting_amount`/`source_total_amount`), без расчёта по рёбрам и без покрытия всей цепочки (`orchestrator/apps/intercompany_pools/pool_domain_steps.py:140`, `orchestrator/apps/intercompany_pools/pool_domain_steps.py:166`).
- Реальный top-down алгоритм с `weight/min/max`, контролем остатка и инвариантом сохранения суммы существует отдельно (`orchestrator/apps/intercompany_pools/distribution.py:29`), но не подключён в execution path.
- Bottom-up агрегатор с проверкой `root_total == total_input_amount` существует отдельно (`orchestrator/apps/intercompany_pools/bottom_up.py:56`), но не используется при workflow runtime execution.
- Publication payload для run/retry сейчас формируется из входного payload (`documents_by_database`) без доказанной связи с расчётом по графу (`orchestrator/apps/intercompany_pools/workflow_runtime.py:552`, `go-services/worker/internal/drivers/poolops/publication_transport.go:195`).

В итоге возможна публикация без гарантии полного покрытия активной цепочки и без строгого доказательства сходимости исходной суммы.

## What Changes
- Зафиксировать, что `pool run` ДОЛЖЕН (SHALL) рассчитывать распределение по активной версии DAG для периода run и использовать этот результат как source-of-truth для publication payload (create path).
- Подключить детерминированные алгоритмы распределения в runtime execution path (`pool.distribution_calculation.top_down`, `pool.distribution_calculation.bottom_up`) вместо summary-only поведения.
- Зафиксировать инварианты full distribution:
  - исходная сумма распределяется без потерь/лишних остатков в пределах денежной точности;
  - активная цепочка организаций, участвующая в публикации, полностью покрыта расчётом;
  - несходимость баланса или gaps покрытия блокируют публикацию fail-closed.
- Зафиксировать machine-readable fail-closed коды для нарушений инвариантов распределения и их проекцию в diagnostics facade.
- Сохранить существующий фасад `/api/v2/pools/runs/*` без breaking изменений публичного URL-контракта.

## Impact
- Affected specs:
  - `pool-distribution-runs`
  - `pool-workflow-execution-core`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/pool_domain_steps.py`
  - `orchestrator/apps/intercompany_pools/distribution.py`
  - `orchestrator/apps/intercompany_pools/bottom_up.py`
  - `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `go-services/worker/internal/drivers/poolops/publication_transport.go` (contract usage unchanged, but вход `documents_by_database` становится расчётным)
  - `orchestrator/apps/intercompany_pools/tests/*`
  - `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py`
- Contracts:
  - публичный pools facade API сохраняется;
  - runtime semantics для distribution/reconciliation/publication payload становятся строже (full-chain + balance guarantees).

## Coordination with sibling changes
- Этот change является upstream для:
  - `add-02-pool-document-policy` (использует distribution artifact как вход compile document chains);
  - `refactor-03-unify-platform-execution-runtime` (использует distribution artifact как вход атомарного workflow compiler).
- В этом change НЕ фиксируются правила document chain/invoice policy; они принадлежат `add-02-pool-document-policy`.
- В этом change НЕ фиксируются platform-wide execution/observability правила (`/operations`, queue-only workflow execute path); они принадлежат `refactor-03-unify-platform-execution-runtime`.

## Non-Goals
- Не менять rollout/auth semantics `pool.publication_odata` (RBAC mapping и related контракты остаются в отдельном change).
- Не вводить новый public endpoint для запуска run.
- Не делать редизайн topology editor или модели `PoolNodeVersion/PoolEdgeVersion`.

## Assumptions
- Под «полным распределением» понимается инвариант по активному DAG для `period_start/period_end`, а не только арифметическая сверка двух полей в summary.
- Для create-run path `documents_by_database` из сырого `run_input` не является authoritative источником, если рассчитанный distribution artifact уже доступен.
- Retry failed-subset сохраняет текущий контракт selective retry, но базируется на ранее рассчитанной/зафиксированной структуре distribution результатов run.
