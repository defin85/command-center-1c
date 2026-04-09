# Change: refactor-workflow-template-compact-catalog-detail

## Почему

После change `04-refactor-ui-platform-workflow-template-workspaces` маршруты `/workflows` и `/templates` формально уже вошли в platform-governed perimeter: у них есть canonical shell, URL-backed selected context и responsive detail fallback. Но по факту обе страницы остались hybrid implementation:
- `MasterDetailShell` с table-first master pane;
- wide columns и horizontal overflow как primary catalog path;
- primary actions и provenance/diagnostics размазаны между row actions, header controls и detail pane.

Из-за этого страницы спорят с более зрелым `catalog-detail` стилем, который уже читается на `/databases` и других compact-selection surfaces. Оператору сложнее быстро просканировать каталог, понять, что именно выбрано, и где находятся главные действия. Визуально и поведенчески это делает `/workflows` и `/templates` похожими на legacy admin grids, а не на каноничные catalog-detail workspaces.

Нужен отдельный change, который завершит normalisation именно этих двух routes: приведёт их к compact `catalog-detail` модели, где master pane отвечает за выбор сущности, а detail pane за inspect, provenance, policy framing и primary actions.

## Что меняется

- Доработать `workflow-management-workspaces`, чтобы `/workflows` был зафиксирован как compact workflow library workspace:
  - scan-friendly selection catalog в master pane;
  - detail-owned primary actions (`inspect/edit/clone/execute` и route handoff);
  - без wide table и icon-first row actions как default primary path.
- Доработать `operation-templates`, чтобы `/templates` был зафиксирован как compact template management workspace:
  - компактный template catalog в master pane;
  - provenance, publish/access state и richer execution contract в detail pane или secondary surfaces;
  - без wide provenance table как основного master-pane представления.
- Зафиксировать route-level expectation, что `/workflows` и `/templates` получают `compact-selection` governance в inventory и проходят существующие lint/browser checks как governed compact catalog routes.
- Зафиксировать, что wide tables, много-колоночные provenance grids и bulk-heavy diagnostics остаются допустимыми только в detail-owned surfaces, dedicated subviews или explicit full-width contexts, а не в primary master pane.

## Impact

- Affected specs:
  - `workflow-management-workspaces`
  - `operation-templates`
- Related specs:
  - `ui-platform-foundation`
  - `ui-frontend-governance`
  - `ui-workspace-presentation-preferences`
- Affected code (expected, when implementing this change):
  - `frontend/src/pages/Workflows/WorkflowList.tsx`
  - `frontend/src/pages/Templates/TemplatesPage.tsx`
  - `frontend/src/uiGovernanceInventory.js`
  - `frontend/src/components/platform/**`
  - `frontend/src/components/platform/__tests__/**`
  - `frontend/tests/browser/**`

## Non-Goals

- Перепроектирование `/workflows/new`, `/workflows/:id`, `/workflows/executions`, `/workflows/executions/:executionId`.
- Изменение backend/API contract templates или workflow persistence.
- Перевод `/templates` и `/workflows` в `catalog-workspace` стиль наподобие `/artifacts`.
- Глобальный user-facing toggle layout modes для всех routes.
- Полная замена всех tabular/detail представлений внутри этих feature areas, если они живут вне primary master pane.

## Assumptions

- Канонический целевой референс для этих двух routes — compact `catalog-detail` стиль, близкий к `/databases`, а не single-pane `catalog-workspace`.
- Existing cross-cutting requirements в `ui-platform-foundation` и `ui-frontend-governance` уже задают общий compact master-pane contract; этот change уточняет route-local truth для `/workflows` и `/templates`.
- Future presentation preferences для compatible routes возможны только после этой normalisation, а не вместо неё.
