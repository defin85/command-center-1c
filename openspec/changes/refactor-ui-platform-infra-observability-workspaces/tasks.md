## 1. Shared governance and platform perimeter
- [ ] 1.1 Расширить `frontend/eslint.config.js` и связанные governance checks с уже migrated routes на `/clusters`, `/system-status` и `/service-mesh`.
- [ ] 1.2 Доработать shared platform primitives и route helpers только там, где текущего thin design layer не хватает для infra/observability catalog, diagnostics и realtime surfaces.

## 2. Infrastructure and observability workspaces
- [ ] 2.1 Мигрировать `/clusters` на canonical management workspace с route-addressable selected cluster/filter context и canonical secondary authoring surfaces для create/edit/discover/credentials flows. (после 1.1)
- [ ] 2.2 Мигрировать `/system-status` на canonical observability workspace с controlled polling state, route-addressable diagnostics context и responsive fallback. (после 1.1; можно выполнять параллельно с 2.1)
- [ ] 2.3 Мигрировать `/service-mesh` на canonical realtime observability workspace с platform-owned shell и responsive fallback для inspect/metrics flows. (после 1.1; можно выполнять параллельно с 2.1 и 2.2)
- [ ] 2.4 Добавить unit/browser regression tests для `/clusters`, `/system-status` и `/service-mesh`: reload/deep-link restore, shell-safe handoff, a11y labels, polling/realtime stability и narrow-viewport fallback. (после 2.1, 2.2 и 2.3)

## 3. Validation
- [ ] 3.1 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- [ ] 3.2 Прогнать `openspec validate refactor-ui-platform-infra-observability-workspaces --strict --no-interactive`.
