## 1. Spec
- [ ] 1.1 Добавить spec delta для `ui-action-catalog-editor` (params template из schema + безопасное auto-fill).

## 2. Frontend (guided modal)
- [ ] 2.1 В `ActionCatalogEditorModal` добавить schema panel (список параметров команды из `params_by_name`).
- [ ] 2.2 Добавить “Insert params template” (и/или safe auto-fill) для `executor.params_json` при выборе `command_id`.
- [ ] 2.3 Фильтрация `disabled` и ibcmd connection params при генерации списка/шаблона.
- [ ] 2.4 Не затирать ручной ввод: tracked `touched` state + confirm при overwrite.

## 3. Tests
- [ ] 3.1 Unit-тест для генерации template (`buildParamsTemplate`) на простых schemas (default/null/repeatable/disabled).
- [ ] 3.2 Playwright: создание нового action → выбор command_id → auto-fill/insert template → Save валиден.

## 4. Validation
- [ ] 4.1 `./scripts/dev/lint.sh --ts`
- [ ] 4.2 `frontend: npm run test:browser:action-catalog` (или покрыть в общем playwright suite)
- [ ] 4.3 `openspec validate add-action-catalog-params-template-from-schema --strict --no-interactive`
