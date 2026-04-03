## 1. Workspace Zones
- [ ] 1.1 Расширить `/pools/master-data` внутри canonical shell зонами `GLAccount` и `GLAccountSet`.
- [ ] 1.2 Добавить forms/list-detail surfaces для `GLAccount`, account bindings и `GLAccountSet` draft/publish/revisions.
- [ ] 1.3 Сделать `chart_identity`, compatibility markers и revision status явными operator-facing полями.

## 2. Shared UI Contracts
- [ ] 2.1 Подключить token picker к generated registry contract и добавить `master_data.gl_account.*.ref`.
- [ ] 2.2 Подключить bindings UI, bootstrap import catalog и sync affordances к generated registry capability policy.
- [ ] 2.3 Показать capability-gated states: bootstrap-only для `GLAccount`, non-actionable profile state для `GLAccountSet`.
- [ ] 2.4 Дочистить shared registry UI helpers после `01`: использовать registry `label` в operator-facing options и убрать оставшиеся string-specific defaults, если они уже не нужны поверх registry contract.

## 3. Verification
- [ ] 3.1 Добавить frontend tests на новые workspace zones, token picker и revision lifecycle.
- [ ] 3.2 Добавить browser tests на canonical shell integration и mobile-safe fallback.
- [ ] 3.3 Прогнать `openspec validate 04-expand-pool-master-data-workspace-for-reusable-accounts --strict --no-interactive`.
