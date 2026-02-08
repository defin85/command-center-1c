## 1. Spec & Contract Alignment
- [x] 1.1 Обновить capability `operation-templates`: `/templates` — единый UI для `template` и `action_catalog`.
- [x] 1.2 Обновить capability `ui-action-catalog-editor`: убрать требование отдельного route `/settings/action-catalog`.
- [x] 1.3 Обновить capability `extensions-action-catalog`: удалить зависимость от runtime setting key `ui.action_catalog`.
- [x] 1.4 Обновить capability `extensions-plan-apply`: закрепить, что выбор action делается только по unified exposures.
- [x] 1.5 Обновить capability `runtime-settings-overrides`: исключить `ui.action_catalog` из поддерживаемых override-ключей.

## 2. Backend Decommission (`ui.action_catalog`)
- [x] 2.1 Удалить `ui.action_catalog` из runtime settings registry и связанной валидации.
- [x] 2.2 Удалить/переписать runtime settings API paths, связанные с `ui.action_catalog` (чтение/запись/override/list).
- [x] 2.3 Удалить legacy код и тесты, где `ui.action_catalog` используется как источник действий.
- [x] 2.4 Оставить effective action catalog read-model только на unified exposures (без fallback к runtime settings).

## 3. Frontend Single-UI Consolidation
- [x] 3.1 Удалить route `/settings/action-catalog` и отдельную страницу `ActionCatalogPage`.
- [x] 3.2 Реализовать в `/templates` переключение surface (`template` / `action_catalog`) с единым редактором.
- [x] 3.3 Обновить меню/навигацию и RBAC-гейтинг под один экран.
- [x] 3.4 Удалить дублирующие frontend-модули action catalog, ставшие лишними после консолидации.

## 4. Contracts, Tests, Verification
- [x] 4.1 Обновить OpenAPI/typed clients для удалённых legacy paths и single-UI контракта.
- [x] 4.2 Обновить backend тесты (runtime settings, action catalog, plan/apply) под отсутствие `ui.action_catalog`.
- [x] 4.3 Обновить frontend тесты роутинга/доступа и сценариев единого редактора.
- [x] 4.4 Прогнать `openspec validate remove-ui-action-catalog-and-unify-operations-ui --strict --no-interactive`.
