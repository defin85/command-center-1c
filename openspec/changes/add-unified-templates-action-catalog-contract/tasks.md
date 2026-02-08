## 1. Spec & Contracts
- [ ] 1.1 Описать unified capability `operation-definitions-catalog` (definition + exposure).
- [ ] 1.2 Добавить capability `operation-templates` и зафиксировать переход templates API на unified persistence.
- [ ] 1.3 Обновить deltas для `extensions-action-catalog`, `extensions-plan-apply`, `ui-action-catalog-editor`.
- [ ] 1.4 Обновить OpenAPI для unified моделей и новых response/request DTO без legacy payload.
- [ ] 1.5 Зафиксировать контракт новых unified endpoints `operation-catalog/*` (list/get/upsert/publish/validate/migration-issues).
- [ ] 1.6 Зафиксировать удаление legacy compatibility flow (`ui.action_catalog` как primary persistence, legacy payload adapters).
- [ ] 1.7 Явно перенести в unified specs все требования `add-set-flags-target-binding-contract` (binding required + schema validation + hints + fail-closed без token guessing).

## 2. Data Model & Migration
- [ ] 2.1 Добавить persistent таблицы unified контракта (`operation_definition`, `operation_exposure`, журнал миграционных проблем).
- [ ] 2.2 Реализовать backfill из `OperationTemplate` в unified store.
- [ ] 2.3 Реализовать backfill из `ui.action_catalog` (global + tenant overrides) в unified store.
- [ ] 2.4 Реализовать дедупликацию definitions по fingerprint с tenant-aware правилами.
- [ ] 2.5 Для `extensions.set_flags` fail-closed: exposure без валидного target binding отмечать как invalid/unpublished.

## 3. Backend Cutover
- [ ] 3.1 Перевести `/api/v2/templates/*` на unified persistence через service-слой.
- [ ] 3.2 Перевести `/api/v2/ui/action-catalog*` на unified persistence через service-слой.
- [ ] 3.3 Перевести `extensions/plan` и `extensions/apply` на резолв actions из unified exposure.
- [ ] 3.4 Удалить/заблокировать legacy write-path для `ui.action_catalog`.
- [ ] 3.5 Удалить legacy adapter-слой payload materialization.
- [ ] 3.6 Реализовать unified endpoints `operation-catalog/*` с RBAC staff/admin и tenant-scope ограничениями.

## 4. Frontend Unification
- [ ] 4.1 Вынести общий adapter `CommandConfig <-> API payload` для `/templates` и `/settings/action-catalog`.
- [ ] 4.2 Обновить `/templates` на unified API без изменения UX и RBAC-семантики.
- [ ] 4.3 Обновить `/settings/action-catalog` на unified API без потери guided/raw UX.
- [ ] 4.4 Убедиться, что `extensions.set_flags.target_binding` редактируется/валидируется по новым hints в unified flow.

## 5. Verification & Rollout
- [ ] 5.1 Добавить backend тесты миграции и чистого cutover без fallback.
- [ ] 5.2 Добавить/обновить frontend unit/browser тесты для обоих экранов на unified backend контракте.
- [ ] 5.3 Подготовить миграционный отчёт (какие actions/templates требуют ручной фиксации).
- [ ] 5.4 Прогнать `openspec validate add-unified-templates-action-catalog-contract --strict --no-interactive`.
