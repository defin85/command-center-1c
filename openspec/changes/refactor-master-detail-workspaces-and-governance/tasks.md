## 1. Platform contract и governance
- [ ] 1.1 Уточнить `ui-platform-foundation` и `ui-frontend-governance` для compact master-pane contract и enforceable lint/browser invariants.
- [ ] 1.2 Добавить или обновить lint-правила, которые fail-close'ят table-first master pane и desktop overflow-prone composition на governed routes.
- [ ] 1.3 Добавить unit coverage для lint governance rules и обновить platform primitives/tests при необходимости.

## 2. Route refactor
- [ ] 2.1 Пересобрать `/operations` вокруг compact master catalog и secondary inspect/detail contract.
- [ ] 2.2 Устранить misleading empty progress/inspect state на `/operations` для zero-task execution.
- [ ] 2.3 Пересобрать `/databases` вокруг compact database catalog в master pane и detail-owned management contexts.
- [ ] 2.4 Пересобрать `/pools/topology-templates` вокруг compact catalog, readable detail summary и недоминирующего guidance layer.

## 3. Verification и docs
- [ ] 3.1 Обновить browser-level regression coverage для `/operations`, `/databases` и `/pools/topology-templates`.
- [ ] 3.2 Прогнать `cd frontend && npm run lint`, `cd frontend && npm run test:run`, `cd frontend && npm run test:browser:ui-platform`, `cd frontend && npm run validate:ui-platform`.
- [ ] 3.3 Прогнать `openspec validate refactor-master-detail-workspaces-and-governance --strict --no-interactive`.
