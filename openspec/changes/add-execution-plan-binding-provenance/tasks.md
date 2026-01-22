## 1. Спеки и контракты
- [ ] 1.1 Добавить новую спецификацию `execution-plan-binding-provenance` (requirements + scenarios).
- [ ] 1.2 Обновить спеки `command-schemas-driver-options`, `ui-action-catalog-editor`, `extensions-action-catalog` с ссылками на новую capability.
- [ ] 1.3 Обновить OpenAPI/контракты: add-only поля и preview endpoint(ы) для plan/provenance.

## 2. Backend (Orchestrator)
- [ ] 2.1 Ввести типы/serializer для `execution_plan` и `bindings[]` (без секретов).
- [ ] 2.2 Реализовать preview endpoint для staff (используют `/databases` drawer и `/settings/action-catalog`).
- [ ] 2.3 Persist: сохранять plan+bindings при создании операции (`execute-ibcmd-cli`/designer) и workflow execution.
- [ ] 2.4 В details endpoints отдавать plan+bindings только staff (и/или по выделенному RBAC разрешению).
- [ ] 2.5 Маскирование: унифицировать redaction для argv и workflow input; добавить тесты на отсутствие секретов в ответах/логах.

## 3. Worker (Go)
- [ ] 3.1 Для runtime-only биндингов репортить `status/reason` в результат (без значений).
- [ ] 3.2 Обеспечить доставку этих данных до Orchestrator и сохранение (пер-task).
- [ ] 3.3 Тесты: unit на репорт биндингов + интеграционный тест пайплайна “worker completed → persisted”.

## 4. Frontend
- [ ] 4.1 `/operations` details: секция “Execution plan” (staff-only), отображает plan + bindings + per-task статусы.
- [ ] 4.2 `/databases` drawer запуска: staff-only preview plan + provenance до запуска.
- [ ] 4.3 `/settings/action-catalog`: кнопка/панель preview для выбранного action (staff-only).
- [ ] 4.4 Тесты UI: smoke для трёх точек (видимость только staff, корректные данные, без утечек).

## 5. Документация
- [ ] 5.1 Обновить `docs/ACTION_CATALOG_GUIDE.md`: “Execution plan / provenance”, что скрыто, где смотреть.
- [ ] 5.2 Добавить раздел “как дебажить” (пример: unsupported flags) и куда смотреть в UI.

## 6. Валидация
- [ ] 6.1 Прогнать `openspec validate add-execution-plan-binding-provenance --strict --no-interactive`.

