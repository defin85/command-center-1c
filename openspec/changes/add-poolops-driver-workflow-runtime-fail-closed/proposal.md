# Change: Ввести poolops-драйвер для workflow worker и fail-closed исполнение pool runtime шагов

## Why
Сейчас в lane `commands:worker:workflows` operation-node может завершаться как `completed` при отсутствии `OperationExecutor` (silent skip), из-за чего шаги `pool.*` фактически не исполняются, включая `publication_odata`.

Это нарушает инварианты `pool-workflow-execution-core` (domain backend + fail-closed) и создаёт ложноположительную проекцию `published` при `workflow_status=completed` без реальной публикации документов.

## What Changes
- Добавить выделенный `poolops`-драйвер/адаптер для исполнения `pool.*` operation nodes в Go workflow worker.
- Закрепить маршрутизацию `pool.*` только через domain executor path (без fallback в generic `odata/cli/ibcmd/ras` драйверы).
- Перевести поведение operation-node в fail-closed при отсутствии executor для pool runtime path (без `execution_skipped=true` как успешного результата).
- Зафиксировать worker->orchestrator контракт статусов с machine-readable `error_code` (и детерминированной ошибкой для pool fail-closed), чтобы код ошибки не терялся между worker/runtime/API.
- Зафиксировать хранение structured failure diagnostics (`error_code`, optional `error_details`) на уровне `WorkflowExecution`, чтобы цепочка `worker -> internal API -> facade` была end-to-end без деградации в текст.
- Зафиксировать canonical internal API-контракт bridge-вызова `poolops` (`path`, request/response schema, retryable/non-retryable статусы, idempotency semantics) в `contracts/orchestrator-internal/openapi.yaml`.
- Зафиксировать single retry owner для bridge-вызовов (без stacked retry между `workflowops` handler и HTTP client transport).
- Уточнить идемпотентность bridge-вызова: один `step_attempt` может иметь несколько transport retries с тем же idempotency key; новый key допускается только при новом `step_attempt`.
- Обновить проекцию pool status: `published/partial_success` допускаются только после подтверждённого завершения publication-step, а не только по агрегатному `workflow:completed`.
- Убрать синтетические переходы `publication_step_state` из агрегатного `workflow status`; source-of-truth для publication-step должен формироваться runtime шагом.
- Зафиксировать explicit migration cutoff source (`runtime_settings` key `pools.projection.publication_hardening_cutoff_utc`, RFC3339 UTC) и формулу `projection_timestamp=coalesce(workflow_execution.started_at, workflow_execution.created_at, pool_run.created_at)`.
- Зафиксировать контракт bridge-взаимодействия `poolops` <-> Orchestrator domain runtime: internal auth, tenant propagation, timeout/retry/idempotency, передача pinned binding provenance (`operation_ref`) и наблюдаемость.
- Зафиксировать обязательное сохранение/проброс `operation_ref` (`binding_mode`, `template_exposure_id`, `template_exposure_revision`) в Go workflow runtime model и bridge payload.
- Зафиксировать в API diagnostics/Problem Details единый machine code: внутренний `error_code` проецируется наружу как `code`; для кейса `workflow=completed` + `publication_step_state!=completed` вводится стабильный код `POOL_PUBLICATION_STEP_INCOMPLETE`.
- Добавить staged migration для projection hardening: historical `workflow_core` run-ы без `publication_step_state` не должны массово переходить в `failed` до завершения migration window/backfill.
- Добавить rollout guardrails: feature-flag/canary + kill-switch для `poolops` маршрута с rollback-safe поведением и сохранением fail-closed инварианта (без возврата к silent-success маршруту).
- Разделить runtime controls для маршрутизации и projection hardening: `poolops` route flag и hardening cutoff/flag должны управляться независимо.
- Выполнять change как блокирующий прод-фикс `poolops + fail-closed + projection hardening`.

## Impact
- Affected specs:
  - `pool-workflow-execution-core`
- Affected code (expected):
  - `go-services/worker/internal/odata/*`
  - `go-services/worker/internal/drivers/poolops/*`
  - `go-services/worker/internal/workflow/handlers/*`
  - `go-services/worker/internal/workflow/engine/*`
  - `go-services/worker/internal/workflow/models/*`
  - `go-services/worker/internal/orchestrator/workflows.go`
  - `go-services/worker/internal/drivers/workflowops/*`
  - `contracts/orchestrator-internal/openapi.yaml`
  - `orchestrator/apps/api_internal/serializers.py`
  - `orchestrator/apps/api_internal/views_workflows.py`
  - `orchestrator/apps/templates/workflow/models_django.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
- Validation:
  - unit/integration tests по маршрутизации `pool.*` и fail-closed поведению;
  - contract tests для canonical bridge endpoint schema + retryable/non-retryable status matrix;
  - unit tests на single retry owner (без retry amplification в stacked слоях);
  - unit/contract tests на идемпотентность: transport retry не меняет step idempotency key, новый key появляется только на новом `step_attempt`;
  - regression tests на kill-switch: `pool.*` не может завершаться `completed` через `execution_skipped=true`;
  - contract tests для передачи `error_code` по цепочке `worker -> internal workflows API -> pools facade diagnostics`;
  - contract tests для persistence `error_code`/`error_details` в `WorkflowExecution` и обратной выдачи в diagnostics;
  - regression tests для stable кода `POOL_PUBLICATION_STEP_INCOMPLETE` в Problem Details;
  - регрессионный test-case против ложного `published` без выполненного `publication_odata`;
  - migration tests для historical `workflow_core` run-ов с `publication_step_state=null` до/после hardening cutoff;
  - end-to-end сценарий run `500` на 3 организации с созданием документов в ИБ.

## Non-Goals
- Не меняем stream topology (`operations`/`workflows`) и deployment split.
- Не переносим pool domain бизнес-логику из Python в Go в рамках этого change.
- Не меняем публичный контракт safe-команд (`confirm-publication`/`abort-publication`) вне необходимой совместимости статусов.
- Не выполняем big-bang рефакторинг всех драйверов в единый универсальный executor.
- Не выполняем в этом change консолидацию общего `odata-core` для всех драйверов; это отдельный follow-up change.
