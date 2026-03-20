# Change: Следующая волна UI platform migration для workflow и template workspaces

## Why
После operational и admin/support волн в authenticated frontend остаётся отдельный слой крупных authoring/catalog surfaces, которые по-прежнему живут на legacy page composition:
- `/workflows`;
- `/workflows/executions`;
- `/workflows/new`;
- `/workflows/:id`;
- `/workflows/executions/:executionId`;
- `/templates`;
- `/pools/templates`;
- `/pools/master-data`.

Эти route особенно чувствительны к page-level UI debt, потому что смешивают authoring, inspect, diagnostics и execute flows в одном canvas, а часть из них вообще обходит `MainLayout` и canonical workspace shell. На практике это выражается в том, что route files остаются крупными и bespoke (`WorkflowDesigner.tsx` и `TemplatesPage.tsx` по `786` строк, `WorkflowMonitor.tsx` — `616` строк), а на route-level composition по-прежнему нет `WorkspacePage`, `PageHeader`, `MasterDetailShell`, `DrawerFormShell`, `ModalFormShell` и других platform primitives.

Нужен отдельный change, который зафиксирует следующую волну migration для workflow/template surfaces, не смешивая её с уже запланированными infra/observability routes.

## What Changes
- Расширить `ui-web-interface-guidelines`, чтобы platform governance perimeter включал `/workflows`, `/workflows/executions`, `/workflows/new`, `/workflows/:id`, `/workflows/executions/:executionId`, `/templates`, `/pools/templates`, `/pools/master-data`.
- Ввести новый capability `workflow-management-workspaces` для route-level UI truth workflow library, workflow designer, workflow executions и workflow monitor.
- Доработать `operation-templates`, чтобы `/templates` был описан как canonical template management workspace, а не только как backend/template contract.
- Доработать `organization-pool-catalog`, чтобы `/pools/templates` был описан как canonical schema template workspace с route-addressable selected template context и canonical authoring surfaces.
- Доработать `pool-master-data-hub-ui`, чтобы `/pools/master-data` был описан как canonical multi-zone workspace с route-addressable active tab/remediation context и mobile-safe fallback.
- Зафиксировать blocking frontend validation gate для этой волны: lint, unit/runtime tests, browser `ui-platform` regressions и production build.

## Impact
- Affected specs:
  - `ui-web-interface-guidelines`
  - `workflow-management-workspaces` (new)
  - `operation-templates`
  - `organization-pool-catalog`
  - `pool-master-data-hub-ui`
- Affected code (expected, when implementing this change):
  - `frontend/src/App.tsx`
  - `frontend/eslint.config.js`
  - `frontend/src/components/platform/**`
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/pages/Templates/**`
  - `frontend/src/pages/Pools/PoolSchemaTemplatesPage.tsx`
  - `frontend/src/pages/Pools/PoolMasterDataPage.tsx`
  - `frontend/tests/browser/**`
  - `frontend/src/components/platform/__tests__/**`

## Non-Goals
- Миграция `/rbac`, `/users`, `/dlq`, `/artifacts`, `/extensions` и `/settings/*`.
- Миграция `/clusters`, `/system-status`, `/service-mesh`.
- Изменение backend runtime semantics workflow execution, templates persistence или master-data API.
- Полная замена всех внутренних workflow widgets, если route-level platform contract уже соблюдён.

## Assumptions
- Shared-shell runtime contract из `refactor-ui-platform-operational-workspaces` считается уже принятой базой и не переопределяется этим change.
- `/templates`, `/pools/templates` и `/pools/master-data` должны оставаться привязанными к своим доменным specs, а не переноситься в новый workflow umbrella capability.
- Workflow list/designer/execution routes достаточно тесно связаны между собой, чтобы их route-level UI truth жил в одном capability `workflow-management-workspaces`.
