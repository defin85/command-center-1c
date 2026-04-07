# Change: Расширить lint coverage UI governance на весь frontend

## Почему
Сейчас UI governance lint покрывает только часть route-page и generic shell-backed `*Modal.tsx`/`*Drawer.tsx` surface. Остальные frontend route-entry модули могут оставаться вне checked-in monitoring perimeter, поэтому новый экран или новый route path можно добавить без явной governance classification.

Это создаёт ложное ощущение, что "линтер уже следит за всем фронтом", хотя на деле текущий контракт остаётся path-based и привязан к отдельным migration wave.

## Что меняется
- Вводится единый repo-wide inventory для operator-facing route-entry modules и shell-backed authoring surfaces.
- Каждый route/module получает явный governance tier: `platform-governed`, `legacy-monitored` или `excluded`.
- Для `platform-governed` route inventory дополнительно фиксирует минимальную route semantics metadata, достаточную для inventory-driven governance rules и browser targeting.
- Frontend lint и governance tests начинают падать, если route или shell-backed surface остаётся без классификации.
- Repo-wide safety rules становятся обязательными для всего frontend perimeter, а более строгие route-level platform rules продолжают применяться к `platform-governed` tier.
- Документация по UI governance обновляется так, чтобы было явно видно, какие исключения допустимы и как новый route должен попадать в monitoring perimeter.

## Impact
- Affected specs: `ui-frontend-governance`
- Affected code: `frontend/eslint.config.js`, `frontend/src/components/platform/__tests__/UiPlatformGovernanceLint.test.ts`, route inventory рядом с `frontend/src/App.tsx`, локальные UI governance docs
- Related changes:
  - `03-refactor-ui-platform-admin-support-workspaces`
  - `archive/2026-04-05-04-refactor-ui-platform-workflow-template-workspaces`
  - `04-refactor-ui-platform-infra-observability-workspaces`
- Non-goals:
  - не мигрировать все legacy route на platform primitives в рамках этого change;
  - не выравнивать весь UI на один одинаково строгий tier за один шаг;
  - не заменять browser-level regressions линтером там, где нужен runtime proof
