## Context
Factual account scope уже является production contract, а не просто локальной настройкой. Поле `account_codes` проходит через:
- workspace defaults;
- preflight/readiness;
- scheduler/runtime fingerprint;
- workflow payload;
- worker transport;
- inspect/replay surfaces.

Если заменить его одномоментно на `GLAccountSet`, rollout станет небезопасным: старые artifacts перестанут исполняться, а rollback потребует пересборки checkpoints.

## Goals / Non-Goals

### Goals
- Перевести factual scope на canonical `GLAccountSet` без big-bang cutover.
- Сохранить replay и rollback для historical artifacts.
- Fail-closed проверять missing reusable account coverage до worker execution.

### Non-Goals
- Не менять top-level factual envelope versions.
- Не делать UI authoring основным предметом этого change.

## Decisions

### Decision: Top-level envelopes остаются `v1`
На bridge-периоде сохраняются `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1`. Версионирование переносится внутрь nested `factual_scope_contract.v2`.

### Decision: Dual-write обязателен
Orchestrator должен одновременно писать:
- `factual_scope_contract.v2` как новый source-of-truth;
- legacy `account_codes` как compatibility projection.

Это позволяет пережить mixed fleet и rollback без пересборки artifacts.

### Decision: Worker и orchestrator работают в dual-read режиме
Новый runtime предпочитает nested `factual_scope_contract.v2` и его pinned `resolved_bindings`, но продолжает корректно исполнять legacy artifacts, выпущенные до cutover или оставшиеся после rollback.

### Decision: Replay использует pinned scope snapshot, а не latest state
Historical replay опирается на persisted `gl_account_set_revision_id`, `effective_members` и `resolved_bindings`. Latest bindings или latest profile revision не должны подменять scope уже созданного factual artifact.

### Decision: Rollout идёт в порядке worker dual-read -> orchestrator dual-write -> backfill -> cutover
Сначала принимающая сторона должна научиться читать новый contract, затем пишущая сторона начинает dual-write, затем выполняется backfill/default revision, и только после этого можно переводить preflight/runtime defaults на `GLAccountSet`.

## Verification Gates
- Worker читает новый nested contract и legacy fallback.
- Historical replay не пересчитывает latest bindings.
- Missing pinned snapshot блокирует replay fail-closed.
- Rollback не требует rebuild factual artifacts.

## Risks / Trade-offs
- Bridge временно удваивает scope data в artifacts.
  - Это допустимая цена за rollback safety.
- Появится дополнительная сложность в preflight и inspect surfaces.
  - Она должна быть явной, потому что скрытая миграция historical scope опаснее.
