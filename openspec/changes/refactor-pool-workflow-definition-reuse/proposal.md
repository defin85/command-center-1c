# Change: Разделить переиспользуемый workflow definition и per-run execution snapshot для pool runtime

## Why
Сейчас pool runtime материализует отдельный `WorkflowTemplate` почти на каждый `Pool Run`, потому что ключ компиляции включает `period_start/period_end` и `run_input`.

Это приводит к двум проблемам:
- `workflows` начинают вести себя как одноразовые операции, а не как переиспользуемые process definitions;
- реестр workflow templates разрастается и усложняет диагностику/поддержку.

Нужно закрепить модель: **definition переиспользуется**, а run-specific данные живут в execution snapshot.

## What Changes
- Вводится явное разделение артефактов:
  - `PoolWorkflowDefinition` (стабильная идентичность процесса);
  - `PoolExecutionPlanSnapshot` (данные конкретного запуска и lineage).
- `definition_key` считается только из структурных признаков процесса (pool/mode/direction/schema version/graph/binding hint) и **не** зависит от `period_*` и `run_input`.
- Для каждого запуска сохраняется immutable execution snapshot, который содержит `period_*`, `run_input`, retry lineage и ссылку на выбранный workflow definition.
- Retry и повторные run-ы с одинаковой структурой переиспользуют тот же workflow definition, но создают новый execution instance со своим snapshot.
- Контракт очереди (`commands:worker:workflows`) и разделение worker deployment’ов (`operations`/`workflows`) остаются без изменений.
- `/templates` явно отображает system-managed pool runtime templates как read-only сущности (без write-path через UI/API).

## Impact
- Affected specs:
  - `pool-workflow-execution-core`
  - `operation-templates`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/workflow_compiler.py`
  - `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  - `orchestrator/apps/templates/workflow/models_django.py`
  - `frontend/src/pages/Templates/*`
  - `frontend/src/api/queries/templates.ts`
- Validation:
  - unit/integration tests compiler/runtime;
  - API/UI tests для `/templates` read-only поведения системных pool templates.

## Non-Goals
- Не меняем бизнес-алгоритмы pool расчётов и публикации.
- Не объединяем `operations` и `workflows` stream в один worker lane.
- Не переводим pool runtime на command-schemas driver model в рамках этого change.
