# Change: Обеспечить полный рабочий цикл pool через UI

## Why
Сейчас оператор может работать через UI только с частью процесса: каталог организаций и шаблоны доступны, но управление самими пулами и топологией отсутствует, а граф на `/pools/catalog` остаётся read-only.

Также запуск run из UI не покрывает direction-specific входные данные для top-down (ввод стартовой суммы) и вынуждает использовать ручные API-вызовы для сценариев полного цикла.

## What Changes
- Расширить функциональность `/pools/catalog` до полного управления пулами:
  - CRUD метаданных пула (`code`, `name`, `is_active`, `description`, `metadata`);
  - редактирование версионируемой топологии пула (узлы/рёбра с `effective_from/effective_to`);
  - сохранение топологии атомарным snapshot-upsert с серверной валидацией DAG-инвариантов;
  - обязательный round-trip `version` token: read endpoint возвращает текущую версию snapshot, update endpoint требует её для optimistic concurrency.
- Расширить `/pools/runs` до полного запуска распределения без ручных HTTP-клиентов:
  - direction-specific run input;
  - для `top_down` — обязательный ввод стартовой суммы пользователем;
  - для `bottom_up` — выбор шаблона и ввод/загрузка входных данных из UI.
- Зафиксировать контракт run creation так, чтобы run input:
  - сохранялся как часть доменной сущности запуска;
  - участвовал в idempotency fingerprint;
  - передавался в workflow input_context для шагов `prepare_input` и `distribution_calculation`.
- **BREAKING** Удалить `source_hash` из публичного create-run контракта и из формулы idempotency key.
- Сохранить читаемость historical run в API/UI после удаления `source_hash` из внешнего контракта:
  - read contract возвращает `run_input` как nullable поле;
  - read contract возвращает `input_contract_version` (`run_input_v1` или `legacy_pre_run_input`).
- Зафиксировать deterministic canonicalization profile для `run_input` (stable key order, deterministic decimal normalization, без зависимости от formatting).
- Унифицировать новые ошибки mutating/create-run endpoint'ов на `application/problem+json` с machine-readable `code`.
- Сохранить и унифицировать end-to-end контроль safe flow в UI (`confirm-publication`, `abort-publication`, retry failed) без выхода в внешние API-клиенты.
- Обновить OpenAPI и generated client/types под новый UI-сценарий.

## Impact
- Affected specs:
  - `organization-pool-catalog`
  - `pool-distribution-runs`
  - `pool-workflow-execution-core`
- Breaking API change:
  - `POST /api/v2/pools/runs/` больше не принимает `source_hash`; клиенты обязаны передавать `run_input`.
  - run read-model удаляет `source_hash` из публичного payload и вводит `run_input` (nullable) + `input_contract_version`.
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
