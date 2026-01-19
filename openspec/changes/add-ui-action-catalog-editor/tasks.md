## 1. Implementation (Реализация)
- [ ] 1.1 UI: добавить staff-only страницу “Action Catalog” (route в settings + пункт меню)
- [ ] 1.2 UI: загрузка текущего `ui.action_catalog` и отображение состояния (guided + raw)
- [ ] 1.3 Guided editor: CRUD действий (id/label/contexts), reorder, copy, toggle enable (через удаление/добавление)
- [ ] 1.4 Guided editor: executor kinds
  - ibcmd_cli: выбор driver + command_id из driver catalog, mode, fixed (timeout/confirm_dangerous), params/additional_args/stdin
  - designer_cli: ввод command + args + fixed, params/stdin (advanced)
  - workflow: выбор workflow template, params (input_context base), fixed
- [ ] 1.5 Raw JSON editor: валидация JSON, форматирование, удобный diff/preview изменений
- [ ] 1.6 Save: PATCH runtime setting + показ ошибок валидации с путями (`extensions.actions[i]...`)
- [ ] 1.7 Контракты/кодген: обновить OpenAPI при необходимости, прогнать `./contracts/scripts/validate-specs.sh`
- [ ] 1.8 Тесты: UI (рендер, переключение режимов, save/error) + backend smoke (валидация по контракту не ломается)
- [ ] 1.9 Docs: краткая инструкция “как настроить action catalog” для операторов

