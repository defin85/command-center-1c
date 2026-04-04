# Change: 03. Перевести factual scope на GLAccountSet через отдельный bridge change

## Why
Текущий factual runtime контракт глубоко завязан на `account_codes`: они используются в workspace defaults, preflight, scope fingerprint, workflow payload и worker transport. Прямая замена этого поля на `GLAccountSet` без моста сломает replay, rollback и совместимость orchestrator/worker.

Поэтому factual migration должна быть отдельным change с собственной rollout-последовательностью и verification gate.

Этот change фиксирует отдельную factual bridge фазу после расширения reusable-data hub account family.

## What Changes
- Ввести first-class quarter-scoped factual scope selection record, keyed by `pool + source_profile + quarter_start`, который выбирает canonical `GLAccountSet` profile и pin-ит одну published revision для всех readiness/runtime paths этого квартала.
- Добавить nested `factual_scope_contract.v2` внутри существующих top-level envelopes `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1`.
- Реализовать dual-write:
  - новый nested scope contract;
  - legacy `account_codes` как compatibility projection.
- Реализовать dual-read в orchestrator и worker на bridge-периоде.
- Сохранять replay-safe factual artifacts с selector key, pinned revision, effective members, resolved bindings и stable scope fingerprint.
- Привязать checkpoint/execution lineage и enqueue idempotency к `scope_fingerprint`, чтобы repin другого revision в том же квартале создавал новый scope lineage, а не маскировался под retry.
- Перевести preflight/runtime/scheduler с hardcoded account codes на quarter-scoped selection record и selected `GLAccountSet` coverage checks.
- Ограничить live chart lookup фазой readiness/preflight: он используется только для materialize/verify `resolved_bindings` snapshot и не остаётся implicit fallback для execution/replay артефактов с `factual_scope_contract.v2`.
- Подготовить backfill/default revision для существующего factual default scope.

## Impact
- Affected specs:
  - `pool-factual-balance-monitoring`
- Affected code:
  - `orchestrator/apps/intercompany_pools/factual_*`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `go-services/worker/internal/drivers/poolops/**`
- Related changes:
  - depends on `02-extend-master-data-hub-with-reusable-accounts`

## Non-Goals
- Изменение top-level factual envelopes c `v1` на новый top-level version.
- Route-level UI migration для `/pools/master-data`.
- Введение отдельного operator-facing authoring UI для quarter-scoped selector; на bridge-фазе selection может оставаться system-managed/backfilled.
- Automatic mutation of chart-of-accounts objects в target ИБ.
