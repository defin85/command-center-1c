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
- Зафиксировать единый authoritative selector path для `pool + source_profile + quarter_start`, чтобы preflight, workspace, scheduler и replay использовали один и тот же pinned revision.

### Non-Goals
- Не менять top-level factual envelope versions.
- Не делать UI authoring основным предметом этого change.

## Decisions

### Decision: Top-level envelopes остаются `v1`
На bridge-периоде сохраняются `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1`. Версионирование переносится внутрь nested `factual_scope_contract.v2`.

### Decision: Authoritative selector живёт в quarter-scoped factual scope selection record
Selected factual account scope не выводится ad hoc из runtime defaults, latest revision или implicit worker logic. Orchestrator вводит first-class selection record, keyed by `pool + source_profile + quarter_start`, который:
- указывает выбранный `GLAccountSet` profile;
- pin-ит конкретную published `GLAccountSet` revision;
- является единственной точкой выбора для workspace defaults, scheduler, preflight и enqueue path;
- может быть system-managed/backfilled на bridge-фазе без отдельного operator-facing UI.

Это снимает ambiguity между pool-level defaults, checkpoint-local seed и source-profile lookup: selection ownership остаётся у orchestrator и materialize-ится до старта worker execution.

### Decision: Dual-write обязателен
Orchestrator должен одновременно писать:
- `factual_scope_contract.v2` как новый source-of-truth;
- legacy `account_codes` как compatibility projection.

Это позволяет пережить mixed fleet и rollback без пересборки artifacts.

### Decision: Worker и orchestrator работают в dual-read режиме
Новый runtime предпочитает nested `factual_scope_contract.v2` и его pinned `resolved_bindings`, но продолжает корректно исполнять legacy artifacts, выпущенные до cutover или оставшиеся после rollback.

Legacy path с live lookup по `account_codes` разрешён только для artifact, который не несёт nested `factual_scope_contract.v2`. Как только artifact уже содержит pinned nested scope contract, runtime обязан считать именно его source-of-truth и не делать silent fallback на latest live lookup.

### Decision: Replay использует pinned scope snapshot, а не latest state
Historical replay опирается на persisted selector key, `gl_account_set_id`, `gl_account_set_revision_id`, `effective_members` и `resolved_bindings`. Latest bindings или latest profile revision не должны подменять scope уже созданного factual artifact.

### Decision: Scope lineage определяется `scope_fingerprint`
`scope_fingerprint` является first-class identity factual scope и вычисляется из quarter-scoped selector key, pinned revision, effective members и bounded quarter context. Этот fingerprint обязан:
- сохраняться в preflight result, checkpoint metadata, workflow input context и inspect surfaces;
- входить в enqueue idempotency key и replay lineage;
- различать `retry same scope` и `new scope for same quarter`.

Если для того же `pool + source_profile + quarter_start` выбирается другая pinned revision, orchestrator должен создать новый scope lineage с новым `scope_fingerprint`, а не переиспользовать существующий retry path.

### Decision: Live chart lookup допускается только для readiness materialization
Live lookup target chart-of-accounts нужен только для того, чтобы в readiness/preflight path materialize или verify `resolved_bindings` snapshot для выбранной pinned revision.

После создания artifact с `factual_scope_contract.v2`:
- worker execution использует только pinned `resolved_bindings`;
- replay использует только pinned `resolved_bindings`;
- отсутствие snapshot считается fail-closed ошибкой;
- live lookup не может silently подменять missing или stale snapshot.

### Decision: Rollout идёт в порядке worker dual-read -> orchestrator dual-write -> backfill -> cutover
Сначала принимающая сторона должна научиться читать новый contract, затем пишущая сторона начинает dual-write, затем выполняется backfill/default revision, и только после этого можно переводить preflight/runtime defaults на `GLAccountSet`.

## Verification Gates
- Quarter-scoped selector record детерминированно резолвит один pinned revision для `pool + source_profile + quarter_start`.
- Worker читает новый nested contract и legacy fallback.
- Новый scope lineage меняет idempotency/fingerprint при repin revision в том же квартале.
- Historical replay не пересчитывает latest bindings.
- Missing pinned snapshot блокирует replay fail-closed.
- Live chart lookup остаётся readiness-only и не используется как fallback для `factual_scope_contract.v2`.
- Rollback не требует rebuild factual artifacts.

## Risks / Trade-offs
- Bridge временно удваивает scope data в artifacts.
  - Это допустимая цена за rollback safety.
- Появится дополнительная сложность в preflight и inspect surfaces.
  - Она должна быть явной, потому что скрытая миграция historical scope опаснее.
