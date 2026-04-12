## 1. OpenSpec And Contracts
- [x] 1.1 Зафиксировать explicit `cluster_all` eligibility contract в `pool-master-data-sync`, `pool-master-data-hub-ui` и `database-metadata-management-ui`, включая tri-state `eligible|excluded|unconfigured`, fail-closed blocking и handoff в `/databases`.
- [x] 1.2 Обновить API/OpenAPI contract для чтения и изменения per-database eligibility state и для machine-readable `cluster_all` resolution diagnostics в manual sync launcher.

## 2. Backend Domain And API
- [x] 2.1 Добавить persisted per-database eligibility state для pool master-data `cluster_all`, с default semantics `unconfigured` для legacy записей.
- [x] 2.2 Изменить `cluster_all` target resolution так, чтобы в snapshot попадали только `eligible` базы, `excluded` публиковались в diagnostics, а `unconfigured` блокировали create request fail-closed.
- [x] 2.3 Сохранить separation of concerns: readiness/runtime health не должны автоматически менять eligibility state, а `database_set` не должен ломаться из-за `cluster_all` membership state.
- [x] 2.4 Добавить API surface на `/databases` для чтения и изменения eligibility state, включая handoff-friendly payload для выбранной базы и кластера.

## 3. Frontend `/databases`
- [x] 3.1 Добавить operator-facing control в `/databases` для просмотра и изменения `cluster_all` eligibility state выбранной ИБ через canonical secondary surface.
- [x] 3.2 Показать объяснение состояний `eligible`, `excluded`, `unconfigured` и separate readiness summary без смешивания этих понятий.
- [x] 3.3 Поддержать deep-link/handoff из consumer surfaces так, чтобы оператор попадал в контекст нужной базы и сразу видел control eligibility.

## 4. Frontend `/pools/master-data`
- [x] 4.1 Расширить `Launch Sync` drawer summary по выбранному кластеру: `eligible`, `excluded`, `unconfigured`.
- [x] 4.2 Блокировать submit для `cluster_all`, если в кластере есть `unconfigured` базы, и показывать явный handoff в `/databases`.
- [x] 4.3 Явно показывать, что `excluded` базы не войдут в launch snapshot, а для one-off исключений оператор может использовать `database_set`.

## 5. Verification
- [x] 5.1 Добавить pytest coverage на persisted eligibility state, `cluster_all` resolution diagnostics, blocking на `unconfigured` и unchanged semantics для `database_set`.
- [x] 5.2 Добавить frontend unit/browser coverage на `/databases` eligibility control и `Sync` launcher diagnostics/handoff.
- [x] 5.3 Прогнать `./scripts/dev/pytest.sh -q <targeted paths>`, `cd frontend && npm run test:run -- <targeted paths>`, при необходимости `cd frontend && npm run test:browser:ui-platform`.
- [x] 5.4 Прогнать `openspec validate add-04-pool-master-data-cluster-all-eligibility-controls --strict --no-interactive`.
