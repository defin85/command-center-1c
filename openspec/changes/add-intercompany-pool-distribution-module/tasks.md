## Scope Boundary
Этот change закрывает только фундамент `pools` (catalog/data/contracts/UI foundation), который не конфликтует с unified runtime.

Execution runtime задачи (фактический запуск run, lifecycle orchestration, provenance/status projection, unified retry/audit semantics) передаются в `refactor-unify-pools-workflow-execution-core`.

## 1. Каталог организаций и пулов (foundation)
- [x] 1.1 Зафиксировать модели `Organization`, `OrganizationPool`, версии узлов/рёбер с `effective_from/to`.
- [x] 1.2 Зафиксировать инварианты графа: DAG, один root, multi-parent только для верхнего уровня.
- [x] 1.3 Зафиксировать связь `организация <-> ИБ` как `1:1`.
- [x] 1.4 Довести внешний sync/refresh контур для master-справочника организаций.
- [x] 1.5 Добавить внешний API для каталога организаций (list/details/upsert/sync trigger) в tenant scope.

## 2. API foundation для пулов и шаблонов
- [x] 2.1 Довести endpoint каталога пулов и графа структуры на дату.
- [x] 2.2 Довести endpoint'ы публичных шаблонов импорта (XLSX/JSON) с опциональной workflow-привязкой.
- [x] 2.3 Сохранить совместимый facade `pools/runs*` как доменный API surface без фиксации отдельного runtime исполнения.

## 3. Контракты и совместимость
- [x] 3.1 Обновить `contracts/orchestrator/openapi.yaml` и связанные контракты для фактических `/api/v2/pools/*` endpoint'ов.
- [x] 3.2 Синхронизировать proxy/client generation, если требуется по контрактному пайплайну проекта.
- [x] 3.3 Добавить API regression тесты по обновлённому pools surface.

## 4. UI foundation
- [x] 4.1 Добавить UI для каталога организаций/пулов с tenant-aware фильтрацией.
- [x] 4.2 Довести UI графа пула как read-oriented представление структуры по дате.
- [x] 4.3 Довести UI шаблонов импорта (XLSX/JSON) с workflow binding.

## 5. Handoff в unified runtime
- [x] 5.1 Явно зафиксировать перенос execution-пунктов в `refactor-unify-pools-workflow-execution-core`.
- [x] 5.2 Зафиксировать migration-совместимость: текущий `pools/runs*` API остаётся фасадом до завершения refactor.

## 6. Качество и валидация
- [x] 6.1 Добавить unit/integration тесты для каталога, графа и sync.
- [x] 6.2 Добавить API contract/regression тесты для foundation endpoint'ов.
- [x] 6.3 Прогнать `openspec validate add-intercompany-pool-distribution-module --strict --no-interactive`.
