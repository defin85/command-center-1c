## 1. Contract

- [x] 1.1 Добавить capability `ui-internationalization-rollout` с end-state требованиями для repo-wide migration remaining operator/staff-facing route families.
- [x] 1.2 Доработать `ui-frontend-governance`, чтобы locale-boundary coverage и completion gates были inventory-backed для всех `platform-governed` route/shell modules.
- [x] 1.3 Доработать `ui-platform-foundation`, чтобы thin design layer явно владел localized shared semantics для page chrome, empty/error/status primitives и shell-backed drawers/modals на всех migrated route families.

## 2. Frontend migration waves

- [x] 2.1 Мигрировать low-coupling admin/support routes: `/extensions`, `/users`, `/dlq`, `/settings/runtime`, `/settings/command-schemas`, `/settings/timeline`. (после 1.1-1.3)
- [x] 2.2 Мигрировать shared support/governance surfaces: `/artifacts`, `/service-mesh`, `/decisions`, включая их owned drawers/detail helpers. (после 2.1)
- [x] 2.3 Мигрировать operational catalog/detail routes: `/operations`, `/databases`, `/templates`. (после 2.2)
- [ ] 2.4 Мигрировать workflow family: `/workflows`, `/workflows/executions`, `/workflows/new`, `/workflows/:id`, `/workflows/executions/:executionId`. (после 2.3)
- [ ] 2.5 Мигрировать pool reusable authoring/catalog surfaces: `/pools/catalog`, `/pools/templates`, `/pools/topology-templates`, `/pools/execution-packs`. (после 2.4)
- [ ] 2.6 Мигрировать `/pools/master-data` и `/pools/runs`. `/pools/factual` закрывается отдельным approved follow-up change и не входит в эту wave. (после 2.5)
- [ ] 2.7 Удалить remaining raw `toLocale*`, hardcoded locale tags и route-local copy registries из scoped route families, их shell surfaces и owned shared helpers. (после 2.1-2.6)

## 3. Governance and verification

- [x] 3.1 Расширить locale governance checks с pilot subset до repo-wide inventory-backed coverage и синхронизировать их с `routeGovernanceInventory` / `shellSurfaceGovernanceInventory` до widening middle/late waves. (после 1.1-1.3; начинать не позже завершения 2.1)
- [ ] 3.2 Добавить unit/integration coverage на новые namespaces, formatter/error-code mappings и locale coverage parity. (после 3.1)
- [ ] 3.3 Добавить browser coverage для representative route families из каждой migration wave, включая language switch + reload и отсутствие mixed-language regressions. (после 3.2)
- [ ] 3.4 Прогнать `cd frontend && npm run lint`, `cd frontend && npm run test:run`, `cd frontend && npm run test:browser:ui-platform`, `openspec validate add-ui-internationalization-rollout --strict --no-interactive`. (после 3.3)
