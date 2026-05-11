# Change: Transition-safe shared shell routing for authenticated frontend

## Why
Во frontend уже есть зафиксированный shared-shell contract, но текущий route tree в [frontend/src/App.tsx](/home/egor/code/command-center-1c/frontend/src/App.tsx) по-прежнему монтирует `ProtectedRoute` / `MainLayout` / `LazyBoundary` почти отдельно для каждого authenticated route.

Пока `BrowserRouter` работает без `future.v7_startTransition`, этот долг в основном маскируется. Как только включается transition-mode, наружу выходит архитектурный дефект handoff: URL меняется, а старый route subtree ещё может владеть shell и stale content. Это уже воспроизводится browser regression'ом на переходе `/service-mesh -> /pools/master-data`, поэтому warning нельзя безопасно заглушить одной строкой.

Нужен отдельный change, который поднимет fix на правильный слой:
- route tree и shared shell ownership;
- bootstrap/authz ownership;
- blocking regression coverage для transition-safe handoff.

## What Changes
- Уточнить `ui-web-interface-guidelines`: shell-backed authenticated routes должны жить под единым route-tree owner для `MainLayout`, shared auth/bootstrap providers и primary suspense boundary.
- Уточнить `ui-realtime-query-runtime`: canonical bootstrap owner должен быть один на authenticated app session, а route-level capability/staff guards должны потреблять shared shell context вместо route-local bootstrap ownership.
- Зафиксировать transition-safe handoff contract для внутренних переходов между authenticated routes без stale content и без redundant bootstrap replay как normal behavior.
- Разрешить explicit exceptions только для login/logout path, dedicated refresh/reset flows и route groups, которые по design остаются authenticated, но no-shell/fullscreen.
- Сделать `future.v7_startTransition` допустимым только после route-tree refactor и blocking regression coverage.

## Impact
- Affected specs:
  - `ui-web-interface-guidelines`
  - `ui-realtime-query-runtime`
- Affected code:
  - `frontend/src/App.tsx`
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/authz/AuthzProvider.tsx`
  - `frontend/src/i18n/I18nProvider.tsx`
  - `frontend/src/authz/**`
  - `frontend/src/api/queries/shellBootstrap.ts`
  - `frontend/src/lib/**`
  - `frontend/src/uiGovernanceInventory.js`
  - `frontend/src/pages/Login/Login.tsx`
  - `frontend/src/components/platform/__tests__/UiGovernanceInventory.test.ts`
  - `frontend/tests/browser/ui-platform-contract-runtime-surfaces.spec.ts`
  - `frontend/src/App*.test.tsx`
- Affected verification:
  - `cd frontend && npm run typecheck`
  - targeted `vitest` for app routing/auth restore
  - `cd frontend && npm run test:browser:ui-platform:runtime-surfaces`

## Non-Goals
- Немедленная миграция на `createBrowserRouter` / `RouterProvider`.
- Big-bang redesign route pages или platform primitives.
- Переписывание domain logic внутри `/service-mesh`, `/pools/master-data` и других route pages, если проблема устраняется на shared-shell слое.
- Любой backend/API contract change.
- Устранение всех возможных duplicate domain reads во всём приложении вне shell/bootstrap ownership.

## Assumptions
- Большинство authenticated routes по-прежнему должны разделять один visual/application shell.
- `workflow` authoring/monitor routes и другие fullscreen surfaces могут остаться no-shell exceptions, но не должны ломать общий auth/bootstrap contract без явного design justification.
- Existing browser regression coverage на `/service-mesh -> /pools/master-data` остаётся canonical proof surface для этой архитектурной проблемы.
