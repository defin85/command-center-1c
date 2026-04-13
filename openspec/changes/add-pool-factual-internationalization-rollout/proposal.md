# Change: add-pool-factual-internationalization-rollout

## Почему

`add-ui-internationalization-rollout` намеренно выводит `/pools/factual` из общего repo-wide scope: route и его shell surface в `frontend/src/uiGovernanceInventory.js` всё ещё помечены как `legacy-monitored`, а сам factual workspace живёт на route-local copy и ad hoc formatting helpers.

В checked-in frontend factual route уже shipped как primary operator workspace, но он пока не использует canonical i18n layer как остальные migrated surfaces:
- `frontend/src/pages/Pools/PoolFactualWorkspacePage.tsx` и `PoolFactualWorkspaceDetail.tsx` держат hardcoded operator copy прямо в route modules;
- `PoolFactualWorkspaceDetail.tsx` использует route-local timestamp/quarter/render helpers вместо shared formatter layer;
- `poolFactualReviewQueue.ts` и `PoolFactualReviewAttributeModal.tsx` владеют review labels/actions локально, без shell-owned translation runtime;
- route и modal остаются вне inventory-backed locale governance completion path.

Параллельно уже есть active change `update-pool-factual-monitoring-sales-report-parity`, но он меняет domain/source-profile semantics factual monitoring, а не locale/governance contract operator workspace. Нужен отдельный follow-up change, который закрывает именно UI internationalization и graduation из `legacy-monitored`.

## Что меняется

- Доработать `pool-factual-balance-monitoring`, чтобы `/pools/factual` workspace, detail surface, review modal и route-owned helper modules использовали canonical frontend i18n runtime, dedicated namespaces, shared locale-aware formatters и code-first localized UI semantics.
- Доработать `ui-frontend-governance`, чтобы factual route и его checked-in shell surface больше не оставались `legacy-monitored`, а входили в inventory-backed locale-boundary governance на тех же основаниях, что и `platform-governed` routes.
- Добавить focused verification для factual workspace: locale switch + reload, detail/modal consistency, отсутствие mixed-language route chrome и route-owned review copy.
- Зафиксировать, что этот change orthogonal к sales-report parity и не меняет factual source-profile/runtime contracts.

## Impact

- Affected specs:
  - `pool-factual-balance-monitoring`
  - `ui-frontend-governance`
- Affected code (expected, when implementing this change):
  - `frontend/src/pages/Pools/PoolFactualPage.tsx`
  - `frontend/src/pages/Pools/PoolFactualWorkspacePage.tsx`
  - `frontend/src/pages/Pools/PoolFactualWorkspaceDetail.tsx`
  - `frontend/src/pages/Pools/PoolFactualReviewAttributeModal.tsx`
  - `frontend/src/pages/Pools/poolFactualReviewQueue.ts`
  - `frontend/src/uiGovernanceInventory.js`
  - `frontend/src/i18n/**`
  - `frontend/eslint.config.js`
  - `frontend/src/pages/Pools/__tests__/PoolFactualPage.test.tsx`
  - `frontend/tests/browser/**`

## Explicitly Out Of Scope

- Изменение factual source profiles, sales-report parity, readiness/preflight или worker/runtime contracts.
- Локализация business/domain payload values из 1C, factual checkpoints и machine-readable scope metadata beyond existing UI mappings.
- Добавление новых locales сверх `ru` и `en`.
- Repo-wide migration других `/pools/*` и non-factual routes; они покрываются `add-ui-internationalization-rollout`.

## Assumptions

- `add-cross-stack-internationalization-foundation` остаётся baseline для shell locale contract, shared runtime и formatter layer.
- `add-ui-internationalization-rollout` и этот change реализуются как separate tracks: repo-wide rollout покрывает `platform-governed` perimeter, а factual follow-up закрывает единственный checked-in `legacy-monitored` operator route.
- `update-pool-factual-monitoring-sales-report-parity` может параллельно менять factual payload semantics, поэтому i18n rollout не должен жёстко привязывать UI к текущему narrow source-profile vocabulary.
