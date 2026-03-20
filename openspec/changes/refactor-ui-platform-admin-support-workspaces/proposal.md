# Change: Следующая волна UI platform migration для admin/support workspaces

## Why
После завершения `refactor-ui-platform-operational-workspaces` в authenticated shell остался отдельный слой legacy route-page, который не входит в platform-governed perimeter и поэтому продолжает накапливать тот же класс проблем, но уже на privileged/admin surfaces.

Сейчас вне нового подхода остаются:
- `/rbac`;
- `/users`;
- `/dlq`;
- `/artifacts`;
- `/extensions`;
- `/settings/runtime`;
- `/settings/command-schemas`;
- `/settings/timeline`.

Это уже не “хвост мелких страниц”, а рабочие поверхности, где по-прежнему смешаны catalog, inspect, authoring и remediation flows, route state почти не зафиксирован в URL, а page-level orchestration держится на raw `antd` containers, bespoke modals/drawers и ad-hoc layouts.

Нужен отдельный change, который зафиксирует следующую волну migration для privileged/admin routes, не смешивая её ни с уже закрытым operational slice, ни с отдельными follow-up epic по workflows и infra/observability.

## What Changes
- Расширить `ui-web-interface-guidelines`, чтобы platform governance perimeter включал `/rbac`, `/users`, `/dlq`, `/artifacts`, `/extensions`, `/settings/runtime`, `/settings/command-schemas`, `/settings/timeline`.
- Зафиксировать новый capability `admin-support-workspaces` для `/rbac`, `/users`, `/dlq` и `/artifacts`, потому что у этих route пока нет собственного UI-level domain contract в OpenSpec.
- Зафиксировать новый capability `settings-management-workspaces` для `/settings/runtime` и `/settings/timeline`, чтобы route-level UI truth не смешивался с backend semantics `runtime-settings-overrides`.
- Доработать `extensions-overview`, чтобы `/extensions` был описан как canonical management workspace с URL-addressable selected extension context и secondary drill-down/authoring surfaces.
- Доработать `command-schemas-driver-options`, чтобы `/settings/command-schemas` был описан как canonical command schema workspace с route-addressable driver/mode/selected command context и responsive fallback.
- Зафиксировать, что blocking frontend gate для этой волны включает lint, unit/runtime tests, browser `ui-platform` regressions и production build.

## Impact
- Affected specs:
  - `ui-web-interface-guidelines`
  - `extensions-overview`
  - `command-schemas-driver-options`
  - `admin-support-workspaces` (new)
  - `settings-management-workspaces` (new)
- Affected code (expected, when implementing this change):
  - `frontend/src/App.tsx`
  - `frontend/eslint.config.js`
  - `frontend/src/components/platform/**`
  - `frontend/src/pages/RBAC/**`
  - `frontend/src/pages/Users/**`
  - `frontend/src/pages/DLQ/**`
  - `frontend/src/pages/Artifacts/**`
  - `frontend/src/pages/Extensions/**`
  - `frontend/src/pages/Settings/**`
  - `frontend/src/pages/CommandSchemas/**`
  - `frontend/tests/browser/**`
  - `frontend/src/components/platform/__tests__/**`

## Non-Goals
- Миграция `/workflows`, `/templates`, `/pools/templates` и `/pools/master-data`.
- Миграция `/clusters`, `/system-status` и `/service-mesh`.
- Изменение backend API, OpenAPI contracts или доменной бизнес-логики.
- Полная leaf-by-leaf замена любого raw `antd` import, если route-level platform contract уже соблюдён.
- Глобальный visual redesign admin/support surfaces вне уже принятого Ant-based platform layer.

## Assumptions
- Shared-shell runtime contract из `refactor-ui-platform-operational-workspaces` считается базовой предпосылкой и не переопределяется этим change.
- `/extensions` и `/settings/command-schemas` остаются в своих доменных capability, а не переносятся в новый umbrella spec.
- `/rbac`, `/users`, `/dlq` и `/artifacts` достаточно близки по характеру operator/admin flows, чтобы их route-level UI truth жил в одном capability без дублирования backend требований.
- `/settings/runtime` и `/settings/timeline` целесообразно описывать вместе как settings management workspaces, даже если backend semantics у них различаются.
