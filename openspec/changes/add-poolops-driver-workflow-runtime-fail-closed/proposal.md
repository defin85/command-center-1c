# Change: Ввести poolops-драйвер для workflow worker и fail-closed исполнение pool runtime шагов

## Why
Сейчас в lane `commands:worker:workflows` operation-node может завершаться как `completed` при отсутствии `OperationExecutor` (silent skip), из-за чего шаги `pool.*` фактически не исполняются, включая `publication_odata`.

Это нарушает инварианты `pool-workflow-execution-core` (domain backend + fail-closed) и создаёт ложноположительную проекцию `published` при `workflow_status=completed` без реальной публикации документов.

## What Changes
- Добавить выделенный `poolops`-драйвер/адаптер для исполнения `pool.*` operation nodes в Go workflow worker.
- Закрепить маршрутизацию `pool.*` только через domain executor path (без fallback в generic `odata/cli/ibcmd/ras` драйверы).
- Перевести поведение operation-node в fail-closed при отсутствии executor для pool runtime path (без `execution_skipped=true` как успешного результата).
- Зафиксировать worker->orchestrator контракт статусов с machine-readable `error_code` (и детерминированной ошибкой для pool fail-closed), чтобы код ошибки не терялся между worker/runtime/API.
- Обновить проекцию pool status: `published/partial_success` допускаются только после подтверждённого завершения publication-step, а не только по агрегатному `workflow:completed`.
- Убрать синтетические переходы `publication_step_state` из агрегатного `workflow status`; source-of-truth для publication-step должен формироваться runtime шагом.
- Зафиксировать контракт bridge-взаимодействия `poolops` <-> Orchestrator domain runtime: internal auth, tenant propagation, timeout/retry/idempotency, передача pinned binding provenance (`operation_ref`) и наблюдаемость.
- Добавить staged migration для projection hardening: historical `workflow_core` run-ы без `publication_step_state` не должны массово переходить в `failed` до завершения migration window/backfill.
- Выполнять change как блокирующий прод-фикс `poolops + fail-closed + projection hardening`.

## Impact
- Affected specs:
  - `pool-workflow-execution-core`
- Affected code (expected):
  - `go-services/worker/internal/odata/*`
  - `go-services/worker/internal/drivers/poolops/*`
  - `go-services/worker/internal/workflow/handlers/*`
  - `go-services/worker/internal/workflow/engine/*`
  - `go-services/worker/internal/orchestrator/workflows.go`
  - `go-services/worker/internal/drivers/workflowops/*`
  - `orchestrator/apps/api_internal/serializers.py`
  - `orchestrator/apps/api_internal/views_workflows.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
- Validation:
  - unit/integration tests по маршрутизации `pool.*` и fail-closed поведению;
  - contract tests для передачи `error_code` по цепочке `worker -> internal workflows API -> pools facade diagnostics`;
  - регрессионный test-case против ложного `published` без выполненного `publication_odata`;
  - migration tests для historical `workflow_core` run-ов с `publication_step_state=null` до/после hardening cutoff;
  - end-to-end сценарий run `500` на 3 организации с созданием документов в ИБ.

## Non-Goals
- Не меняем stream topology (`operations`/`workflows`) и deployment split.
- Не переносим pool domain бизнес-логику из Python в Go в рамках этого change.
- Не меняем публичный контракт safe-команд (`confirm-publication`/`abort-publication`) вне необходимой совместимости статусов.
- Не выполняем big-bang рефакторинг всех драйверов в единый универсальный executor.
- Не выполняем в этом change консолидацию общего `odata-core` для всех драйверов; это отдельный follow-up change.
