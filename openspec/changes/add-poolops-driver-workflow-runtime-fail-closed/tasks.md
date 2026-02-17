## 1. Spec & Contracts
- [ ] 1.1 Уточнить требования `pool-workflow-execution-core` для маршрутизации `pool.*` через выделенный execution path в workflow worker (без fallback в generic драйверы).
- [ ] 1.2 Зафиксировать fail-closed поведение при отсутствии pool executor (runtime error вместо `execution_skipped` успеха).
- [ ] 1.3 Уточнить правила status projection: `published/partial_success` только при подтверждённом завершении publication-step.
- [ ] 1.4 Зафиксировать контракт internal status update (`error_code`, `error_message`, optional `error_details`) и правила его persistence/propagation в diagnostics facade.
- [ ] 1.5 Зафиксировать canonical bridge endpoint `POST /api/v2/internal/workflows/execute-pool-runtime-step` в `contracts/orchestrator-internal/openapi.yaml` (request/response schemas + status matrix).
- [ ] 1.6 Зафиксировать bridge payload-контракт с pinned binding provenance (`operation_ref.alias`, `operation_ref.binding_mode`, `template_exposure_id`, `template_exposure_revision`).
- [ ] 1.7 Зафиксировать single retry owner для bridge/status update path (retry owner = transport client, без stacked retry между handler и transport client).
- [ ] 1.8 Зафиксировать cutoff source и формулу projection timestamp: runtime setting `pools.projection.publication_hardening_cutoff_utc` + `coalesce(workflow_execution.started_at, workflow_execution.created_at, pool_run.created_at)`.
- [ ] 1.9 Зафиксировать внешний diagnostics mapping: internal `error_code` -> Problem Details `code`, включая `POOL_PUBLICATION_STEP_INCOMPLETE`.
- [ ] 1.10 Зафиксировать idempotency semantics: `step_attempt` vs `transport_attempt`, reuse idempotency key в рамках одного `step_attempt`.
- [ ] 1.11 Зафиксировать rollout policy: kill-switch отключает `poolops` route без возврата в legacy silent-success path.

## 2. Worker: poolops execution path
- [ ] 2.1 Добавить `poolops`-драйвер/адаптер и wiring в workflow engine (`OperationExecutor` dependency injection).
- [ ] 2.2 Реализовать маршрутизацию `pool.*` operation types только в `poolops` path; запретить fallback в generic drivers.
- [ ] 2.3 Реализовать fail-closed обработку misconfiguration (нет executor/adapter) с machine-readable ошибкой.
- [ ] 2.4 Реализовать bridge-клиент на canonical internal endpoint с internal auth, tenant propagation, timeout, status-based retry classification и idempotency key per `step_attempt`.
- [ ] 2.5 Убрать retry amplification: оставить единый retry owner и удалить внешний retry-loop там, где транспорт уже ретраит.
- [ ] 2.6 Обновить Go workflow runtime model/operation request для обязательного проброса `operation_ref` (`binding_mode`, `template_exposure_id`, `template_exposure_revision`) до bridge payload.
- [ ] 2.7 Обновить worker->orchestrator client path для передачи `error_code`/`error_details` в `update-execution-status`.
- [ ] 2.8 Добавить fail-closed guard для kill-switch (`POOL_RUNTIME_ROUTE_DISABLED`) без возврата к `execution_skipped`-success маршруту.

## 3. Orchestrator: projection hardening
- [ ] 3.1 Обновить rules в pool run projection, чтобы исключить `published` при `workflow:completed` без подтверждённого publication-step результата.
- [ ] 3.2 Убрать/пересобрать синтетические переходы `publication_step_state` из агрегатного workflow status updater.
- [ ] 3.3 Реализовать internal API обработку `error_code`/`error_details` в update-status serializer/view/model для WorkflowExecution.
- [ ] 3.4 Обеспечить обратную совместимость historical run-ов и стабильные diagnostics в API.
- [ ] 3.5 Реализовать staged migration для `workflow_core` historical run-ов с `publication_step_state=null` (cutoff/backfill + rollback-safe поведение).
- [ ] 3.6 Добавить runtime setting `pools.projection.publication_hardening_cutoff_utc` (registry/default/docs) и использовать canonical projection timestamp.
- [ ] 3.7 Возвращать `POOL_PUBLICATION_STEP_INCOMPLETE` в Problem Details `code` для кейса `workflow=completed` + `publication_step_state!=completed`.
- [ ] 3.8 Добавить persistence structured diagnostics в `WorkflowExecution` (`error_code`, optional `error_details`) и миграцию схемы/контрактов.

## 4. Rollout
- [ ] 4.1 Добавить feature flag для включения `poolops` route.
- [ ] 4.2 Добавить canary rollout policy для части workflow workers.
- [ ] 4.3 Добавить kill-switch для отключения `poolops` route в fail-closed режиме (без legacy silent-success fallback).
- [ ] 4.4 Развести runtime controls для `poolops` routing и projection hardening (независимое управление).

## 5. Validation
- [ ] 5.1 Unit tests: routing `pool.*`, fail-closed при отсутствии executor, отсутствие `execution_skipped`-success для pool path.
- [ ] 5.2 Integration tests: `publication_odata` реально исполняется, создаются publication attempts/documents.
- [ ] 5.3 Regression tests: сценарий “workflow completed без публикации” не проецируется как `published`.
- [ ] 5.4 Observability tests: трассировка bridge-вызовов, retry-счётчики, fail-closed ошибки с machine-readable кодами.
- [ ] 5.5 Contract tests: `WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED` проходит по цепочке `worker -> internal API -> facade diagnostics`.
- [ ] 5.6 Contract tests: canonical bridge endpoint schema + retryable/non-retryable status matrix.
- [ ] 5.7 Unit tests: single retry owner (нет retry amplification при временных сбоях).
- [ ] 5.8 Regression tests: `POOL_PUBLICATION_STEP_INCOMPLETE` стабильно возвращается в Problem Details `code`.
- [ ] 5.9 Migration tests: historical `workflow_core` run (до cutoff) остаётся читаемым без forced `failed`, новый run (после cutoff) fail-closed.
- [ ] 5.10 Contract tests: transport retry в рамках одного `step_attempt` переиспользует тот же idempotency key.
- [ ] 5.11 Regression tests: kill-switch возвращает `POOL_RUNTIME_ROUTE_DISABLED` и не допускает `execution_skipped`-success.
- [ ] 5.12 Contract tests: `error_code`/`error_details` сохраняются в `WorkflowExecution` и возвращаются в facade diagnostics.
- [ ] 5.13 Прогнать `openspec validate add-poolops-driver-workflow-runtime-fail-closed --strict --no-interactive`.
