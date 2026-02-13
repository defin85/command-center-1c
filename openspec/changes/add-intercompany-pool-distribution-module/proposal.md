# Change: Добавить модуль межорганизационного распределения и публикации через OData

## Why
Текущий orchestrator покрывает сервисные операции по ИБ, но не поддерживает сквозной контур межорганизационного распределения продаж/покупок с контролем баланса и массовой публикацией в 1С через OData.

Бизнесу нужен единый модуль, который:
- управляет иерархическими пулами организаций,
- считает распределения сверху-вниз и снизу-вверх,
- публикует документы в несколько ИБ,
- даёт прозрачный аудит и сводную сверку движений.

## What Changes
- Закрыть фундамент домена `pools` как data/catalog layer:
  - master-справочник организаций и пулов;
  - модель пула как DAG с версионностью (`effective_from/to`);
  - связь `организация <-> ИБ` как `1:1`;
  - внешний sync/refresh контур для каталога организаций.
- Зафиксировать и довести foundation API/UI:
  - каталог пулов и граф структуры по дате;
  - публичные шаблоны импорта (XLSX/JSON) с опциональной workflow-привязкой;
  - совместимый фасад `pools/runs*` на уровне API-контракта без фиксации отдельного runtime.
- Обновить `contracts/**` для фактически поддерживаемого surface `/api/v2/pools/*`.
- Явно передать execution-область в `refactor-unify-pools-workflow-execution-core`:
  - фактическое исполнение run,
  - lifecycle orchestration и status projection,
  - run provenance через workflow runtime,
  - унификацию retry/audit semantics на execution-core.

## Impact
- Affected specs:
  - `organization-pool-catalog` (primary scope)
  - `pool-distribution-runs` (execution часть переносится в `refactor-unify-pools-workflow-execution-core`)
  - `pool-odata-publication` (execution часть переносится в `refactor-unify-pools-workflow-execution-core`)
- Affected code (high-level):
  - `orchestrator/apps/intercompany_pools/**` (domain foundation)
  - `orchestrator/apps/api_v2/views/intercompany_pools.py` (foundation API/facade)
  - `contracts/**` (публичный контракт pools endpoint'ов)
  - `frontend/src/pages/Pools/**` (foundation UI: каталог/граф/шаблоны)

## Non-Goals
- Полная бухгалтерская методология и настройка всех видов проводок в рамках одного change.
- Универсальный коннектор ко всем внешним форматам файлов в первом релизе (основной фокус: XLSX и JSON).
- Изменение существующей общей модели RBAC за пределами добавления ролей/прав модуля.
- Финализация отдельного runtime исполнения `pools` (run lifecycle orchestration, execution provenance, unified retries) в этом change.
