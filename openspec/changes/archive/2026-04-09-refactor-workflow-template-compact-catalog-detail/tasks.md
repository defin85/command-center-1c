## 1. Route contract and governance alignment

- [x] 1.1 Зафиксировать в route-level specs, что `/workflows` и `/templates` используют compact `catalog-detail` модель, где master pane отвечает только за scan/select, а primary actions и плотная metadata живут в detail.
- [x] 1.2 Выразить для `/workflows` и `/templates` route-level `compact-selection` governance expectation в inventory и acceptance matrix, не меняя их `workspaceKind`. (после 1.1)

## 2. `/templates` compact catalog-detail normalisation

- [x] 2.1 Пересобрать primary master pane `/templates` как compact template catalog без wide provenance grid и horizontal overflow как default primary path. (после 1.1)
- [x] 2.2 Перенести publish/access/provenance density и richer execution contract в detail pane и canonical secondary surfaces, сохранив route-addressable selected template context. (после 2.1)
- [x] 2.3 Добавить targeted unit/browser coverage для `/templates`: reload/deep-link restore, compact master pane, отсутствие primary horizontal overflow и detail-owned actions. (после 2.2)

## 3. `/workflows` compact catalog-detail normalisation

- [x] 3.1 Пересобрать primary master pane `/workflows` как compact workflow selection catalog без wide table и icon-first row actions как default primary path. (после 1.1)
- [x] 3.2 Перенести `inspect/edit/clone/execute` и related diagnostics handoff в detail-owned action cluster или explicit route handoff, сохранив URL-backed selected workflow context. (после 3.1)
- [x] 3.3 Добавить targeted unit/browser coverage для `/workflows`: reload/deep-link restore, compact master pane, отсутствие primary horizontal overflow и detail-owned actions. (после 3.2)

## 4. Validation

- [x] 4.1 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- Примечание: `2026-04-09` подтверждён полностью зелёный wrapper-run `npm --prefix frontend run build`, включая `generate:api`, `lint`, `test:run`, `test:browser:ui-platform` и `build:assets`.
- [x] 4.2 Прогнать `openspec validate refactor-workflow-template-compact-catalog-detail --strict --no-interactive`.
