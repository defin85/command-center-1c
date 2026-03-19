# Change: improve-decisions-binding-profiles-usability

## Почему
- `/decisions` и `/pools/binding-profiles` уже переведены на canonical platform layer, но их текущий UX остаётся тяжёлым для повседневой работы аналитика и оператора.
- На обеих страницах primary workspace state живёт только в локальном React state, поэтому deep-link, back/forward и повторное открытие конкретного контекста работают хуже, чем ожидается от stateful admin surfaces.
- В обоих маршрутах есть keyboard/accessibility и discoverability gaps: placeholder-only controls без устойчивого accessible name, selection patterns с несемантичными trigger-элементами или mouse-first поведением, слабый selected-state.
- `/decisions` перегружен равноправными действиями и ранним выводом metadata/diagnostics, тогда как `/pools/binding-profiles` показывает opaque pins и raw payload слишком рано, ещё до operator-facing summary и next-step контекста.

## Что меняется
- Уточняется usability contract для `/decisions` в `workflow-decision-modeling`.
- Уточняется usability contract для `/pools/binding-profiles` в `pool-binding-profiles`.
- Уточняются общие web interface guidelines для:
  - persistent labels у shell/table-toolbar/form controls;
  - semantic selection patterns в master-detail surfaces;
  - URL-addressable route state для stateful workspace pages.
- Change задаёт конкретный remediation plan по порядку внедрения:
  - shared labels и common interaction baseline;
  - URL-state и selection patterns;
  - `/decisions` action hierarchy и progressive disclosure;
  - `/pools/binding-profiles` summary-first detail hierarchy.

## Impact
- Affected specs:
  - `workflow-decision-modeling`
  - `pool-binding-profiles`
  - `ui-web-interface-guidelines`
- Affected code (expected, when implementing this change):
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/pages/Decisions/DecisionsPage.tsx`
  - `frontend/src/pages/Decisions/DecisionCatalogPanel.tsx`
  - `frontend/src/pages/Decisions/DecisionDetailPanel.tsx`
  - `frontend/src/pages/Decisions/useDecisionsCatalog.ts`
  - `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`
  - route-level tests for `/decisions` and `/pools/binding-profiles`
  - browser smoke / UI governance checks
- Related planned work:
  - `add-decision-revision-transfer-workbench` должен опираться на resulting `/decisions` workspace contract и не переintroduce competing action hierarchy.

## Не-цели
- Полный visual redesign всего admin shell.
- Новый global design system change поверх уже принятой UI platform.
- Изменение backend API, OpenAPI contracts или бизнес-логики `decision`/`binding_profile`.
- Общий URL-state framework для всего frontend, если route-local implementation закрывает задачу проще.
- Полная перепись всех catalog/detail страниц вне `/decisions` и `/pools/binding-profiles`.

## Предпосылки
- Existing platform primitives (`WorkspacePage`, `PageHeader`, `MasterDetailShell`, `EntityList`, `EntityTable`, `EntityDetails`, `JsonBlock`) остаются canonical foundation и не заменяются.
- Для этого change usability считается частью default runtime contract, а не cosmetic follow-up: если primary state нельзя шарить по URL или keyboard-selection остаётся неявным, change нельзя считать завершённым.
