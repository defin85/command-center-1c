# Change: Harden `/pools/binding-profiles` after UI audit

## Why
`/pools/binding-profiles` уже переведён на новый platform layer, но аудит страницы выявил несколько реальных дефектов, которые ещё не закреплены как explicit contract:
- на narrow viewport primary detail actions и secondary data blocks в drawer остаются хрупкими;
- default detail path всё ещё показывает opaque immutable pin там, где оператору нужен summary-first экран;
- часть operator-facing text/controls не проходит WCAG AA по контрасту;
- есть heading-order и accessible-name defects, воспроизводимые прямо на странице через shared shell.

Текущие specs хорошо покрывают dedicated catalog surface и structured authoring, но не фиксируют:
- что technical immutable ids должны оставаться advanced-only на default detail path;
- что inspect/revise/deactivate flow обязан оставаться mobile-safe и touch-safe;
- что shared shell/status/button/heading contracts, проявляющиеся на этой странице, должны соответствовать базовым accessibility expectations.

Нужен узкий remediation change, который закроет audit findings без расползания в broad redesign всего UI.

## What Changes
- Уточнить `pool-binding-profiles` contract для summary-first detail hierarchy на `/pools/binding-profiles`.
- Зафиксировать, что immutable opaque pins и raw technical payload остаются explicit advanced disclosure, а не default operator content.
- Зафиксировать mobile-safe/touch-safe inspect flow для detail drawer и catalog selection на `/pools/binding-profiles`.
- Уточнить `ui-web-interface-guidelines` для:
  - visible label / accessible name parity у interactive controls;
  - sequential heading hierarchy;
  - WCAG AA contrast для operator-facing text, status indicators и action labels на platform-governed surfaces и shared shell.
- Ограничить implementation scope страницей `/pools/binding-profiles` и shared primitives/shell pieces, которые нужны для прохождения этого аудита.

## Impact
- Affected specs:
  - `pool-binding-profiles`
  - `ui-web-interface-guidelines`
- Affected code (expected, when implementing this change):
  - `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`
  - `frontend/src/components/platform/MasterDetailShell.tsx`
  - `frontend/src/components/platform/EntityTable.tsx`
  - `frontend/src/components/platform/StatusBadge.tsx`
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/App.tsx` or shared theme/token wiring if contrast remediation needs theme-level fix
  - page/browser tests for `/pools/binding-profiles`

## Non-Goals
- Полный visual redesign admin shell или menu system.
- Broad accessibility cleanup всех routes в рамках одного change.
- Переписывание `/pools/catalog`, `/pools/runs` или других operational surfaces.
- Изменение backend API, runtime contracts или business logic `binding_profile`.
- Новая общая design-token strategy поверх уже существующего UI platform direction.

## Assumptions
- Opaque `binding_profile_revision_id` остаётся authoritative runtime identity и не убирается из продукта; change меняет только default disclosure level на operator-facing detail path.
- Shared shell fixes допустимы только там, где без них audit findings этой страницы остаются невыполненными.
- Изменения контраста предпочтительно делать через shared theme/status primitives, а не через page-local one-off overrides, если это не расширяет scope beyond this audit remediation.
- Этот change должен быть совместим с уже созданным `refactor-ui-platform-operational-workspaces` и не подменяет его broader migration plan.
