# Change: Следующая волна UI platform migration для infrastructure и observability workspaces

## Why
После operational, admin/support и workflow/template волн в authenticated shell остаётся компактный, но всё ещё legacy слой infrastructure/observability routes:
- `/clusters`;
- `/system-status`;
- `/service-mesh`.

Эти pages меньше по масштабу, чем предыдущие slices, но по-прежнему не входят в platform-governed perimeter и поэтому продолжают жить на bespoke layouts:
- `Clusters.tsx` — `556` строк raw tables/modals/actions;
- `SystemStatus.tsx` — raw `Card/Row/Col` page assembly и ручной polling canvas;
- `ServiceMeshPage.tsx` — custom div/css shell без platform route primitives.

Нужен отдельный завершающий change для infra/observability routes, чтобы убрать остаточный legacy perimeter и зафиксировать единый platform contract на authenticated frontend.

## What Changes
- Расширить `ui-web-interface-guidelines`, чтобы platform governance perimeter включал `/clusters`, `/system-status` и `/service-mesh`.
- Ввести новый capability `infra-observability-workspaces` для route-level UI truth этих surfaces.
- Зафиксировать `/clusters` как canonical management workspace с selected cluster context и canonical secondary authoring surfaces.
- Зафиксировать `/system-status` как canonical observability workspace с controlled polling state, route-addressable diagnostics context и responsive fallback.
- Зафиксировать `/service-mesh` как canonical realtime observability workspace с platform-owned shell и responsive fallback вместо bespoke full-page div layout.
- Зафиксировать blocking frontend validation gate для этой волны: lint, unit/runtime tests, browser `ui-platform` regressions и production build.

## Impact
- Affected specs:
  - `ui-web-interface-guidelines`
  - `infra-observability-workspaces` (new)
- Affected code (expected, when implementing this change):
  - `frontend/src/App.tsx`
  - `frontend/eslint.config.js`
  - `frontend/src/components/platform/**`
  - `frontend/src/pages/Clusters/**`
  - `frontend/src/pages/SystemStatus/**`
  - `frontend/src/pages/ServiceMesh/**`
  - `frontend/tests/browser/**`
  - `frontend/src/components/platform/__tests__/**`

## Non-Goals
- Миграция workflow/template routes.
- Миграция admin/support routes.
- Изменение backend semantics cluster sync, system health API или realtime service mesh transport.
- Полный redesign observability widgets, если route-level platform contract уже соблюдён.

## Assumptions
- Shared-shell runtime contract и platform primitives из предыдущих waves уже приняты и переиспользуются без пересмотра.
- Infra/observability routes достаточно малы и близки по характеру operator workflows, чтобы их route-level truth жил в одном capability `infra-observability-workspaces`.
