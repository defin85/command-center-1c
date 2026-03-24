# Change: add-pool-topology-template-catalog-workspace

## Why

`/pools/catalog` уже зависит от topology template catalog как от consumer surface: оператору предлагается выбрать `topology_template_revision` и назначить организации в slot-ы. Но в shipped UI нет отдельного operator-facing path, где эти reusable topology templates можно создать или выпустить новую revision.

В результате current UX обрывается на сообщении `Выберите revision из topology template catalog`, хотя сам catalog в SPA заполнить нельзя. Оператору приходится выходить из штатного интерфейса и использовать прямые API-вызовы или служебные инструменты вне product surface. Это ломает expected authoring flow и делает template-based instantiation неполным как основной путь тиражирования topology.

Нужен отдельный canonical producer workspace:
- dedicated route для list/detail/create/revise topology templates;
- явный handoff из `/pools/catalog` в этот route;
- возврат в topology task context выбранного `pool`, чтобы reusable authoring и concrete instantiation оставались связным операторским сценарием.

## What Changes

- Добавить новую capability `pool-topology-template-catalog` для operator-facing route `/pools/topology-templates`.
- Зафиксировать, что route использует existing topology template API для:
  - list topology templates;
  - create topology template с initial revision;
  - create новой revision для уже существующего template.
- Зафиксировать, что `/pools/catalog` остаётся consumer path для instantiation и НЕ author'ит reusable topology template inline.
- Добавить explicit handoff из `/pools/catalog` в `/pools/topology-templates`, когда:
  - topology template catalog пуст;
  - оператору нужно создать новую reusable схему;
  - оператору нужно выпустить новую revision reusable topology.
- Зафиксировать возврат из `/pools/topology-templates` обратно в pool topology context без повторного ручного выбора `pool` и topology task.
- Зафиксировать platform-first page composition для нового surface: dedicated workspace, canonical form shells, mobile-safe detail fallback.

## Impact

- Affected specs:
  - `pool-topology-template-catalog`
  - `organization-pool-catalog`
- Affected code:
  - `frontend/src/App.tsx`
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/pages/Pools/PoolCatalogRouteCanvas.tsx`
  - `frontend/src/pages/Pools/PoolTopologyTemplatesPage.tsx`
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/api/intercompanyPools.contracts.ts`
  - `frontend/tests/browser/**`
  - `docs/observability/WORKFLOW_CENTRIC_POOLS_RUNBOOK.md`
- Explicitly out of scope:
  - новая backend domain model для topology templates;
  - graph-to-template extraction из существующего manual `pool`;
  - automatic conversion existing `pool` в reusable topology template;
  - lifecycle actions вроде deactivate/archive для topology template, если их не требует current backend contract.
