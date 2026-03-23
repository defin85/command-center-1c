## 1. Contracts

- [x] 1.1 Добавить capability `pool-topology-template-catalog` с dedicated operator-facing workspace для list/detail/create/revise topology templates.
- [x] 1.2 Расширить `organization-pool-catalog` требования явным handoff из `/pools/catalog` в reusable topology template workspace.

## 2. Frontend Workspace

- [x] 2.1 Добавить route `/pools/topology-templates` и navigation entry для topology template catalog.
- [x] 2.2 Реализовать platform-based catalog/detail workspace для topology templates и их revisions.
- [x] 2.3 Реализовать create flow для нового topology template с initial revision и revise flow для существующего template.
- [x] 2.4 Добавить typed frontend API wrappers и contract assertions для topology template list/create/revise surfaces.
- [x] 2.5 Добавить explicit handoff/return path между `/pools/catalog` и `/pools/topology-templates`, сохраняя selected `pool` и topology task context.

## 3. Documentation And Validation

- [x] 3.1 Обновить operator docs/runbook: где author'ятся topology templates и как вернуться в `/pools/catalog` для instantiation.
- [x] 3.2 Добавить/update frontend tests на catalog workspace, create/revise flows и handoff return context.
- [x] 3.3 Добавить/update contract/docs parity tests для topology template UI surface.
- [x] 3.4 Прогнать релевантные quality gates: targeted `npm run lint`, `npm run test:run`, `npm run test:browser`, `openspec validate add-pool-topology-template-catalog-workspace --strict --no-interactive`.
