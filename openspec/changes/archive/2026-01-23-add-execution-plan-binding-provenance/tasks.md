## 1. Спеки и контракты
- [x] 1.1 Добавить новую спецификацию `execution-plan-binding-provenance` (requirements + scenarios).
- [x] 1.2 Обновить спеки `command-schemas-driver-options`, `ui-action-catalog-editor`, `extensions-action-catalog` с ссылками на новую capability.
- [x] 1.3 Обновить OpenAPI/контракты: add-only поля и preview endpoint(ы) для plan/provenance.

## 2. Backend (Orchestrator)
- [x] 2.1 Ввести типы/serializer для `execution_plan` и `bindings[]` (без секретов).
- [x] 2.2 Реализовать preview endpoint для staff (используют `/databases` drawer и `/settings/action-catalog`).
- [x] 2.3 Persist: сохранять plan+bindings при создании операции (`execute-ibcmd-cli`/designer) и workflow execution.
- [x] 2.4 В details endpoints отдавать plan+bindings только staff (и/или по выделенному RBAC разрешению).
- [x] 2.5 Маскирование: унифицировать redaction для argv и workflow input; добавить тесты на отсутствие секретов в ответах/логах.

## 3. Worker (Go)
- [x] 3.1 Для runtime-only биндингов репортить `status/reason` в результат (без значений).
- [x] 3.2 Обеспечить доставку этих данных до Orchestrator и сохранение (пер-task).
- [x] 3.3 Тесты: unit на репорт биндингов + интеграционный тест пайплайна “worker completed → persisted”.

## 4. Frontend
- [x] 4.1 `/operations` details: секция “Execution plan” (staff-only), отображает plan + bindings + per-task статусы.
- [x] 4.2 `/databases` drawer запуска: staff-only preview plan + provenance до запуска.
- [x] 4.3 `/settings/action-catalog`: кнопка/панель preview для выбранного action (staff-only).
- [x] 4.4 Тесты UI: smoke для трёх точек (видимость только staff, корректные данные, без утечек).

## 5. Документация
- [x] 5.1 Обновить `docs/ACTION_CATALOG_GUIDE.md`: “Execution plan / provenance”, что скрыто, где смотреть.
- [x] 5.2 Добавить раздел “как дебажить” (пример: unsupported flags) и куда смотреть в UI.

## 6. Валидация
- [x] 6.1 Прогнать `openspec validate add-execution-plan-binding-provenance --strict --no-interactive`.
