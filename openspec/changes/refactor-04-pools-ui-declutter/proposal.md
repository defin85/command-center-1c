# Change: Рефакторинг Pools UI для снижения когнитивной перегрузки

## Why
Страницы `/pools/catalog` и `/pools/runs` одновременно показывают слишком много независимых сценариев (управление данными, мониторинг, диагностика, safe-команды, retry), из-за чего оператору сложно быстро понять «что делать сейчас».

Для операторского diagnostics UX на `/pools/runs` нужен стабильный observability contract из `refactor-03-unify-platform-execution-runtime`; без этого UI-слой получает высокий риск повторных переделок.

На `/pools/templates` базовый edit-flow уже введён в рамках текущего цикла работ, но его нужно удержать как baseline и проверить совместимость после declutter-рефакторинга.

## What Changes
- Перестроить информационную архитектуру `/pools/catalog` в task-oriented рабочие зоны, чтобы оператор видел только релевантные действия для текущего шага.
- Перестроить `/pools/runs` в stage-based workflow (create/inspect/safe/retry) с progressive disclosure для тяжёлых диагностических блоков.
- Уменьшить визуальный шум: скрыть advanced JSON/diagnostics по умолчанию и показывать их только по явному действию.
- Зафиксировать sequencing: UI diagnostics интеграция с расширенными runtime полями выполняется после стабилизации контрактов в `refactor-03-unify-platform-execution-runtime`.
- Сохранить и регрессионно подтвердить существующий `/pools/templates` edit-flow (create/edit modal + update endpoint) как обязательный baseline.
- Сохранить существующие доменные инварианты, tenant-safety guard'ы и backend-контракты run/pool lifecycle.

## Impact
- Affected specs:
  - `organization-pool-catalog`
  - `pool-distribution-runs`
- Affected code (expected):
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/pages/Pools/PoolRunsPage.tsx`
  - `frontend/src/pages/Pools/PoolSchemaTemplatesPage.tsx`
  - `frontend/src/api/intercompanyPools.ts`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_v2/urls.py`
  - `contracts/orchestrator/src/openapi.yaml`
  - `contracts/orchestrator/openapi.yaml`
- Dependencies:
  - `refactor-03-unify-platform-execution-runtime` (stabilized observability fields for diagnostics integrations).

## Non-Goals
- Не менять доменную математику распределения и lifecycle run.
- Не вводить новую RBAC-модель или новый tenant-resolution механизм.
- Не делать глобальный редизайн всего приложения вне страниц `/pools/*`.

## Assumptions
- Базовый navigation shell приложения остаётся прежним; изменения ограничены контентом страниц `/pools/catalog`, `/pools/runs`, `/pools/templates`.
- Refactor должен быть backward-compatible по API для существующих операторских сценариев.
- На этапе, когда `refactor-03` ещё не завершён, UI допускает временный backward-compatible рендер diagnostics без новых observability полей, но финальная интеграция выполняется только после стабилизации контракта.
