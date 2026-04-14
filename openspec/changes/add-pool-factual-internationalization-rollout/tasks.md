## 1. Contract

- [x] 1.1 Доработать `pool-factual-balance-monitoring`, чтобы operator-facing factual workspace был обязан использовать canonical frontend i18n runtime, dedicated factual namespaces и shared formatter boundaries.
- [x] 1.2 Доработать `ui-frontend-governance`, чтобы `/pools/factual` и его checked-in shell surfaces не могли завершить migration, оставаясь `legacy-monitored`.

## 2. Frontend factual route migration

- [x] 2.1 Добавить/расширить factual route namespaces и shared UI mappings для page chrome, alerts, empty/error states, review labels/actions и route-owned fallback copy. (после 1.1-1.2)
- [x] 2.2 Мигрировать `PoolFactualWorkspacePage.tsx` и `PoolFactualWorkspaceDetail.tsx` на canonical translation hooks и shared formatter layer, убрав route-local user-facing copy и ad hoc formatting helpers как primary path. (после 2.1)
- [x] 2.3 Мигрировать `PoolFactualReviewAttributeModal.tsx` и `poolFactualReviewQueue.ts` на canonical localized semantics, сохранив machine-readable review payload contract. (после 2.2)
- [x] 2.4 Обновить `frontend/src/uiGovernanceInventory.js`, locale-boundary checks и related governance tests так, чтобы factual route/shell slice проходил inventory-backed coverage как migrated surface, а не `legacy-monitored` исключение. (после 2.3)

## 3. Verification

- [x] 3.1 Добавить/обновить unit coverage для factual route copy, formatter-backed rendering и review-action labels/errors. (после 2.4)
- [x] 3.2 Добавить browser coverage для `/pools/factual`: locale switch + reload, detail-open state и modal/review consistency без mixed-language regressions. (после 3.1)
- [x] 3.3 Прогнать `cd frontend && npm run lint`, `cd frontend && npm run test:run -- src/pages/Pools/__tests__/PoolFactualPage.test.tsx`, `cd frontend && npm run test:browser:ui-platform`, `openspec validate add-pool-factual-internationalization-rollout --strict --no-interactive`. (после 3.2)
