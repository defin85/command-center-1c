## 1. Platform contract и governance
- [x] 1.1 Уточнить `ui-platform-foundation` и `ui-frontend-governance` для compact master-pane contract и inventory-driven lint/browser invariants.
- [x] 1.2 Добавить или обновить lint-правила, которые fail-close'ят table-first master pane и desktop overflow-prone composition на governed routes, используя shared governance inventory вместо отдельного hand-maintained route списка.
- [x] 1.3 Добавить unit coverage для lint governance rules и при необходимости расширить shared governance inventory/tests для targeting `MasterDetail` routes.

## 2. Route refactor
- [x] 2.1 Пересобрать `/operations` вокруг compact master catalog и secondary inspect/detail contract.
- [x] 2.2 Устранить misleading empty progress/inspect state на `/operations` для zero-task execution.
- [x] 2.3 Пересобрать `/databases` вокруг compact database catalog в master pane и detail-owned management contexts.
- [x] 2.4 Пересобрать `/pools/topology-templates` вокруг compact catalog, readable detail summary и недоминирующего guidance layer.

## 3. Verification и docs
- [x] 3.1 Обновить browser-level regression coverage для `/operations`, `/databases` и `/pools/topology-templates`.
- [x] 3.2 Прогнать `cd frontend && npm run lint`, `cd frontend && npm run test:run`, `cd frontend && npm run test:browser:ui-platform`, `cd frontend && npm run validate:ui-platform`.
- [x] 3.3 Прогнать `openspec validate 02-refactor-master-detail-workspaces-and-governance --strict --no-interactive`.
