# Change: Обеспечить полный рабочий цикл pool через UI

## Why
Сейчас оператор может работать через UI только с частью процесса: каталог организаций и шаблоны доступны, но управление самими пулами и топологией отсутствует, а граф на `/pools/catalog` остаётся read-only.

Также запуск run из UI не покрывает direction-specific входные данные для top-down (ввод стартовой суммы) и вынуждает использовать ручные API-вызовы для сценариев полного цикла.

## What Changes
- Расширить функциональность `/pools/catalog` до полного управления пулами:
  - CRUD метаданных пула (`code`, `name`, `is_active`, `description`, `metadata`);
  - редактирование версионируемой топологии пула (узлы/рёбра с `effective_from/effective_to`);
  - сохранение топологии атомарным snapshot-upsert с серверной валидацией DAG-инвариантов.
- Расширить `/pools/runs` до полного запуска распределения без ручных HTTP-клиентов:
  - direction-specific run input;
  - для `top_down` — обязательный ввод стартовой суммы пользователем;
  - для `bottom_up` — выбор шаблона и ввод/загрузка входных данных из UI.
- Зафиксировать контракт run creation так, чтобы run input:
  - сохранялся как часть доменной сущности запуска;
  - участвовал в idempotency fingerprint;
  - передавался в workflow input_context для шагов `prepare_input` и `distribution_calculation`.
- Зафиксировать совместимость перехода на `run_input`:
  - historical run без `run_input` остаются читаемыми в API/UI;
  - на переходном этапе допускается legacy `source_hash`, но `run_input` является каноническим source-of-truth для нового fingerprint.
- Сохранить и унифицировать end-to-end контроль safe flow в UI (`confirm-publication`, `abort-publication`, retry failed) без выхода в внешние API-клиенты.
- Обновить OpenAPI и generated client/types под новый UI-сценарий.

## Impact
- Affected specs:
  - `organization-pool-catalog`
  - `pool-distribution-runs`
  - `pool-workflow-execution-core`
- Affected code (expected):
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/pages/Pools/PoolRunsPage.tsx`
  - `frontend/src/api/intercompanyPools.ts`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_v2/urls.py`
  - `contracts/orchestrator/openapi.yaml`

## Dependencies
- Change логически опирается на `update-organization-catalog-management-ui` и расширяет покрытие от управления организациями до полного pool lifecycle.

## Non-Goals
- Визуальный drag-and-drop редактор графа (в MVP допускается формо- и табличное редактирование топологии).
- Изменение бизнес-правил распределения (алгоритм/формулы) вне текущих доменных спецификаций.
- Отдельный «новый runtime» для pools: используется текущий unified workflow runtime.
- Перевод старых клиентов на `run_input` в рамках одного релиза без переходного периода совместимости.
