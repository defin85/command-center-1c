## 1. Scope Selector And Contract Bridge
- [x] 1.1 Ввести first-class quarter-scoped factual scope selection record, keyed by `pool + source_profile + quarter_start`, который pin-ит selected `GLAccountSet` profile и published revision.
- [x] 1.2 Ввести nested `factual_scope_contract.v2` внутри текущих factual `v1` envelopes и включить в него selector key, `gl_account_set_id`, `gl_account_set_revision_id`, `effective_members`, `resolved_bindings`, `scope_fingerprint`.
- [x] 1.3 Реализовать orchestrator dual-write для nested scope contract и legacy `account_codes` compatibility projection.
- [x] 1.4 Реализовать worker/orchestrator dual-read с приоритетом pinned nested scope contract.

## 2. Runtime Lineage And Authority
- [x] 2.1 Перевести factual preflight на selected `GLAccountSet` coverage и fail-closed blockers по `gl_account`/binding completeness.
- [x] 2.2 Ограничить live chart lookup фазой readiness/preflight: materialize/verify `resolved_bindings` snapshot до enqueue и запретить silent fallback в execution/replay для artifact с `factual_scope_contract.v2`.
- [x] 2.3 Привязать checkpoint metadata, workflow input, inspect surfaces и enqueue idempotency к `scope_fingerprint`, чтобы repin другого revision в том же квартале создавал новый scope lineage.
- [x] 2.4 Перевести scheduler/runtime defaults с hardcoded account codes на quarter-scoped selection record и selected pinned revision.
- [x] 2.5 Подготовить backfill/default-compatible `GLAccountSet` revision и selection record для текущего production scope.
- [x] 2.6 Зафиксировать replay/inspect surfaces на pinned `resolved_bindings`, а не latest lookup.

## 3. Verification
- [x] 3.1 Добавить tests на selection record, nested scope contract, dual-write, dual-read и rollback compatibility.
- [x] 3.2 Добавить tests на scope lineage/idempotency: retry same scope переиспользует fingerprint, а repin revision в том же квартале создаёт новый lineage.
- [x] 3.3 Добавить tests на historical replay с pinned bindings snapshot и fail-closed отсутствие snapshot без live fallback.
- [x] 3.4 Провести live rehearsal cutover/rollback на factual artifacts. Evidence: `artifacts/2026-04-05-live-cutover-rollback-evidence.md`
- [x] 3.5 Прогнать `openspec validate 03-bridge-pool-factual-scope-to-gl-account-set --strict --no-interactive`.
