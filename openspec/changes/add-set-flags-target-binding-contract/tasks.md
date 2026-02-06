## 1. Spec & Contracts
- [ ] 1.1 Обновить OpenSpec deltas для `extensions-action-catalog`, `extensions-plan-apply`, `ui-action-catalog-editor`.
- [ ] 1.2 Уточнить OpenAPI/сериализаторы для нового поля `executor.target_binding.extension_name_param` (только для `extensions.set_flags`).

## 2. Backend (Orchestrator)
- [ ] 2.1 Расширить schema `ui.action_catalog`: добавить `executor.target_binding.extension_name_param`.
- [ ] 2.2 Добавить fail-closed validation на update-time runtime setting:
- [ ] 2.2.1 Для `capability="extensions.set_flags"` поле `target_binding.extension_name_param` обязательно.
- [ ] 2.2.2 Binding-параметр должен существовать в `params_by_name` выбранного `command_id`.
- [ ] 2.3 Обновить plan/apply: подставлять request `extension_name` в bound param перед preview/execute.
- [ ] 2.4 Возвращать `CONFIGURATION_ERROR` при отсутствующем/некорректном binding до создания операции.
- [ ] 2.5 Добавить/обновить backend тесты (валидация action catalog + plan/apply для set_flags).

## 3. Frontend (Action Catalog Editor)
- [ ] 3.1 Обновить backend hints endpoint для `extensions.set_flags` с полем `target_binding`.
- [ ] 3.2 Добавить guided-поле в editor modal для ввода `target_binding.extension_name_param`.
- [ ] 3.3 Показывать серверные ошибки валидации по пути `executor.target_binding...` без “тихих” локальных fallback.
- [ ] 3.4 Обновить frontend unit/browser тесты для editor flow.

## 4. Validation
- [ ] 4.1 Прогнать релевантные backend тесты (`pytest`) для runtime settings и extensions plan/apply.
- [ ] 4.2 Прогнать frontend тесты (Vitest/Playwright) для Action Catalog editor.
- [ ] 4.3 Прогнать `openspec validate add-set-flags-target-binding-contract --strict --no-interactive`.
