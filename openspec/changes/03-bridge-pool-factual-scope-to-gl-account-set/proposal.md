# Change: 03. Перевести factual scope на GLAccountSet через отдельный bridge change

## Why
Текущий factual runtime контракт глубоко завязан на `account_codes`: они используются в workspace defaults, preflight, scope fingerprint, workflow payload и worker transport. Прямая замена этого поля на `GLAccountSet` без моста сломает replay, rollback и совместимость orchestrator/worker.

Поэтому factual migration должна быть отдельным change с собственной rollout-последовательностью и verification gate.

Этот change фиксирует отдельную factual bridge фазу после расширения reusable-data hub account family.

## What Changes
- Ввести selected pinned `GLAccountSet` revision как canonical source-of-truth для bounded factual account scope.
- Добавить nested `factual_scope_contract.v2` внутри существующих top-level envelopes `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1`.
- Реализовать dual-write:
  - новый nested scope contract;
  - legacy `account_codes` как compatibility projection.
- Реализовать dual-read в orchestrator и worker на bridge-периоде.
- Сохранять replay-safe factual artifacts с pinned revision, effective members, resolved bindings и stable scope fingerprint.
- Перевести preflight/runtime/scheduler с hardcoded account codes на selected `GLAccountSet` coverage checks.
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
- Automatic mutation of chart-of-accounts objects в target ИБ.
