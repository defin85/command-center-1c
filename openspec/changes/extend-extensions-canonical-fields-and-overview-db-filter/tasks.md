## 1. Backend (Orchestrator)
- [x] 1.1 Расширить канонический `extensions_inventory` (mapping) полями `purpose/safe_mode/unsafe_action_protection`
- [x] 1.2 Обновить `/api/v2/extensions/overview/`: добавить `database_id` и реализовать семантику “ограничить список имён по выбранной базе”
- [x] 1.3 Покрыть тестами: канонизация дополнительных полей + фильтр `database_id` (включая RBAC/tenant)

## 2. Frontend
- [x] 2.1 Добавить фильтр “Database” на странице `/extensions` (select/search по доступным базам)
- [x] 2.2 Пробросить `database_id` в запрос `/api/v2/extensions/overview/`
- [x] 2.3 В drill-down drawer сделать отдельную фильтрацию по базе (независимо от верхней таблицы)
- [x] 2.4 Добавить UI-тесты/юнит-тесты для нового фильтра (минимально: корректная передача параметров и сброс пагинации)

## 3. Contracts / Docs
- [x] 3.1 Обновить OpenAPI/контракты для `/api/v2/extensions/overview/` (query `database_id`) и сгенерированные клиенты (если применимо)
- [x] 3.2 Обновить `docs/*` или spec Purpose (если нужно) кратким описанием фильтра по базе

## 4. Validation
- [x] 4.1 `./scripts/dev/pytest.sh` (релевантные тесты)
- [x] 4.2 `./scripts/dev/lint.sh --python` + `./scripts/dev/lint.sh --ts`
