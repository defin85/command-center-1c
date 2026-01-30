## 1. Контракт tenant context (spec)
- [x] Добавить/обновить spec “tenancy tenant context”: алгоритм выбора tenant и правила ошибок.

## 2. Единый механизм tenant context
- [x] Выбрать единый entrypoint установки tenant context (без дублирования в permission/view).
- [x] Убедиться, что thread-local tenant и `request.tenant_id` выставляются консистентно и очищаются между запросами.

## 3. Упрощение v2 endpoints
- [x] Убрать ad-hoc проверки tenant context из view (где возможно), опираясь на единый механизм.
- [x] Убедиться, что tenant-scoped чтение/запись использует один и тот же источник tenant context.

## 4. Тесты
- [x] Перевести tenancy-related тесты на аутентификацию, проходящую реальный pipeline (без `force_authenticate`), либо предоставить поддерживаемый helper.
- [x] Добавить/обновить тесты на сценарии: header tenant, preference tenant, отсутствие membership, сервисный user.

## 5. Contracts
- [x] Обновить `contracts/orchestrator/openapi.yaml` через `spectacular`.
- [x] Прогнать `./contracts/scripts/validate-specs.sh` и `./contracts/scripts/generate-all.sh`.
