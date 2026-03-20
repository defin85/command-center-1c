## 1. Shared governance and platform perimeter
- [ ] 1.1 Расширить `frontend/eslint.config.js` и связанные governance checks с operational perimeter на `/rbac`, `/users`, `/dlq`, `/artifacts`, `/extensions`, `/settings/runtime`, `/settings/command-schemas`, `/settings/timeline`.
- [ ] 1.2 Доработать shared platform primitives и route helpers только там, где текущего thin design layer не хватает для privileged catalog/detail/authoring surfaces и responsive fallback.

## 2. Admin and support catalog workspaces
- [ ] 2.1 Мигрировать `/rbac` и `/users` на canonical admin workspaces с URL-addressable selected mode/tab/entity context и canonical secondary authoring surfaces. (после 1.1)
- [ ] 2.2 Мигрировать `/dlq` и `/artifacts` на canonical remediation/catalog workspaces с selected entity context, shell-safe operational handoff и mobile-safe detail fallback. (после 1.1; можно выполнять параллельно с 2.1)
- [ ] 2.3 Добавить unit/browser regression tests для `/rbac`, `/users`, `/dlq` и `/artifacts`: reload/deep-link restore, shell-safe handoff, a11y labels и narrow-viewport fallback. (после 2.1 и 2.2)

## 3. Extensions and settings workspaces
- [ ] 3.1 Мигрировать `/extensions` на canonical management workspace с URL-addressable selected extension context, secondary drill-down surface и template/manual-operation authoring через canonical shells. (после 1.1)
- [ ] 3.2 Мигрировать `/settings/runtime` и `/settings/timeline` на canonical settings workspaces с route-addressable section/selection context, secondary diagnostics/remediation surfaces и responsive fallback. (после 1.1; можно выполнять параллельно с 3.1)
- [ ] 3.3 Мигрировать `/settings/command-schemas` на canonical command schema workspace с route-addressable driver/mode/selected command context и mobile-safe fallback для inspect/editor path. (после 1.1; можно выполнять параллельно с 3.1 и 3.2)
- [ ] 3.4 Добавить unit/browser regression tests для `/extensions`, `/settings/runtime`, `/settings/timeline` и `/settings/command-schemas`: deep-link restore, same-route stability, shell-safe handoff и responsive fallback. (после 3.1, 3.2 и 3.3)

## 4. Validation
- [ ] 4.1 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- [ ] 4.2 Прогнать `openspec validate refactor-ui-platform-admin-support-workspaces --strict --no-interactive`.
