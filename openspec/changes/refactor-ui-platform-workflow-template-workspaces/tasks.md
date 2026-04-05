## 1. Shared governance and platform perimeter
- [ ] 1.1 Расширить `frontend/eslint.config.js` и связанные governance checks с уже migrated routes на `/workflows`, `/workflows/executions`, `/workflows/new`, `/workflows/:id`, `/workflows/executions/:executionId`, `/templates`, `/pools/templates`, `/pools/master-data`.
- [ ] 1.2 Доработать shared platform primitives и route helpers только там, где текущего thin design layer не хватает для workflow/template authoring, inspect и diagnostics surfaces.

## 2. Workflow management workspaces
- [ ] 2.1 Мигрировать `/workflows` и `/workflows/executions` на canonical workflow catalog workspaces с URL-addressable selected filters/entity context, shell-safe handoff и mobile-safe detail fallback. (после 1.1)
- [ ] 2.2 Мигрировать `/workflows/new`, `/workflows/:id` и `/workflows/executions/:executionId` на canonical workflow authoring/monitor workspaces с route-addressable editor/selected node context и responsive fallback для inspect flows. (после 1.1; можно выполнять параллельно с 2.1)
- [ ] 2.3 Добавить unit/browser regression tests для workflow routes: reload/deep-link restore, same-route stability, shell-safe handoff и narrow-viewport fallback. (после 2.1 и 2.2)

## 3. Template and master-data workspaces
- [ ] 3.1 Мигрировать `/templates` на canonical template management workspace с route-addressable selected template context и canonical authoring surfaces. (после 1.1)
- [ ] 3.2 Мигрировать `/pools/templates` на canonical schema template workspace с route-addressable selected template context и canonical secondary authoring surfaces. (после 1.1; можно выполнять параллельно с 3.1)
- [ ] 3.3 Мигрировать `/pools/master-data` на canonical multi-zone workspace shell с route-addressable active tab/remediation context и responsive fallback вместо raw tab canvas как единственного page shell, не включая reusable-account domain expansion и account-specific helper adapters. (после 1.1; можно выполнять параллельно с 3.1 и 3.2)
- [ ] 3.4 Добавить unit/browser regression tests для `/templates`, `/pools/templates` и `/pools/master-data`: deep-link restore, shell-safe handoff, a11y labels и responsive fallback. Для `/pools/master-data` acceptance ограничить route shell/state contract и не включать post-platform reusable-account surfaces. (после 3.1, 3.2 и 3.3)

## 4. Validation
- [ ] 4.1 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- [ ] 4.2 Прогнать `openspec validate refactor-ui-platform-workflow-template-workspaces --strict --no-interactive`.
