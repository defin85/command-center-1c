## 1. Scope Contract Bridge
- [ ] 1.1 Ввести nested `factual_scope_contract.v2` внутри текущих factual `v1` envelopes.
- [ ] 1.2 Реализовать orchestrator dual-write для `gl_account_set_revision_id`, `effective_members`, `resolved_bindings`, `scope_fingerprint` и legacy `account_codes`.
- [ ] 1.3 Реализовать worker/orchestrator dual-read с приоритетом pinned nested scope contract.

## 2. Runtime Cutover
- [ ] 2.1 Перевести factual preflight на selected `GLAccountSet` coverage и fail-closed blockers.
- [ ] 2.2 Перевести scheduler/runtime defaults с hardcoded account codes на selected pinned revision.
- [ ] 2.3 Подготовить backfill/default-compatible `GLAccountSet` revision для текущего production scope.
- [ ] 2.4 Зафиксировать replay/inspect surfaces на pinned `resolved_bindings`, а не latest lookup.

## 3. Verification
- [ ] 3.1 Добавить tests на nested scope contract, dual-write, dual-read и rollback compatibility.
- [ ] 3.2 Добавить tests на historical replay с pinned bindings snapshot и fail-closed отсутствие snapshot.
- [ ] 3.3 Провести live rehearsal cutover/rollback на factual artifacts.
- [ ] 3.4 Прогнать `openspec validate 03-bridge-pool-factual-scope-to-gl-account-set --strict --no-interactive`.
