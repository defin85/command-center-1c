# Change: Ввести poolops-драйвер для workflow worker и fail-closed исполнение pool runtime шагов

## Why
Сейчас в lane `commands:worker:workflows` operation-node может завершаться как `completed` при отсутствии `OperationExecutor` (silent skip), из-за чего шаги `pool.*` фактически не исполняются, включая `publication_odata`.

Это нарушает инварианты `pool-workflow-execution-core` (domain backend + fail-closed) и создаёт ложноположительную проекцию `published` при `workflow_status=completed` без реальной публикации документов.

## What Changes
- Добавить выделенный `poolops`-драйвер/адаптер для исполнения `pool.*` operation nodes в Go workflow worker.
- Закрепить маршрутизацию `pool.*` только через domain executor path (без fallback в generic `odata/cli/ibcmd/ras` драйверы).
- Перевести поведение operation-node в fail-closed при отсутствии executor для pool runtime path (без `execution_skipped=true` как успешного результата).
- Обновить проекцию pool status: `published/partial_success` допускаются только после подтверждённого завершения publication-step, а не только по агрегатному `workflow:completed`.
- Убрать синтетические переходы `publication_step_state` из агрегатного `workflow status`; source-of-truth для publication-step должен формироваться runtime шагом.
- Добавить общий переиспользуемый транспортный слой `odata-core` (auth/session/retry/error mapping/batch helpers), который используют `odataops` (generic CRUD) и `poolops` (шаг `publication_odata`).
- Выполнять change по этапам: Этап 1 — `poolops + fail-closed + projection hardening` (блокирующий прод-фикс); Этап 2 — вынесение shared `odata-core` и переключение `poolops`/`odataops` на него (без изменения доменной семантики).

## Impact
- Affected specs:
  - `pool-workflow-execution-core`
- Affected code (expected):
  - `go-services/worker/internal/odata/*`
  - `go-services/worker/internal/drivers/odataops/*`
  - `go-services/worker/internal/drivers/poolops/*`
  - `go-services/worker/internal/workflow/handlers/*`
  - `go-services/worker/internal/workflow/engine/*`
  - `go-services/worker/internal/drivers/workflowops/*`
  - `orchestrator/apps/api_internal/views_workflows.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
- Validation:
  - unit/integration tests по маршрутизации `pool.*` и fail-closed поведению;
  - регрессионный test-case против ложного `published` без выполненного `publication_odata`;
  - end-to-end сценарий run `500` на 3 организации с созданием документов в ИБ.

## Non-Goals
- Не меняем stream topology (`operations`/`workflows`) и deployment split.
- Не переносим pool domain бизнес-логику из Python в Go в рамках этого change.
- Не меняем публичный контракт safe-команд (`confirm-publication`/`abort-publication`) вне необходимой совместимости статусов.
- Не выполняем big-bang рефакторинг всех драйверов в единый универсальный executor.
