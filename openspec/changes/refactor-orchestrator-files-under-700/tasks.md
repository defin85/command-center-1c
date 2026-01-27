## 0. Подготовка
- [ ] 0.1 Зафиксировать список orchestrator файлов >700 строк (по правилам из `add-file-size-guideline-700`).
- [ ] 0.2 Определить целевую структуру пакетов для `api_v2/views` (подпакеты по доменам).

## 1. Разнос views (api_v2)
- [ ] 1.1 `views/rbac.py`: разнести на `views/rbac/*` (permissions/roles/refs/audit/compat) с сохранением публичных импортов.
- [ ] 1.2 `views/operations.py`: разнести на `views/operations/*` (execute/query/audit/helpers).
- [ ] 1.3 `views/driver_catalogs.py`: разнести на подмодули (read/write/validate/audit).
- [ ] 1.4 `views/workflows.py`, `views/databases.py`, `views/ui.py`, `views/clusters.py`, `views/artifacts.py`: аналогично (по ответственности).

## 2. Разнос сервисов
- [ ] 2.1 Крупные сервисы (`operations_service.py`, `databases/services.py`, `ibcmd_catalog_v2.py`): выделить подмодули по операциям/подсистемам.

## 3. Тесты
- [ ] 3.1 Разнести крупные тестовые модули на несколько файлов по сценариям (например, editor/execute/permissions).
- [ ] 3.2 Убедиться, что имена и фикстуры остаются понятными и переиспользуемыми.

## 4. Валидация
- [ ] 4.1 `./scripts/dev/lint.sh` (ruff + др.)
- [ ] 4.2 `pytest` (релевантные пакеты/полный прогон по договорённости)
- [ ] 4.3 `openspec validate refactor-orchestrator-files-under-700 --strict --no-interactive`

