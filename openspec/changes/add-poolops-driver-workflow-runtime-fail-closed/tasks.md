## 1. Spec & Contracts
- [ ] 1.1 Уточнить требования `pool-workflow-execution-core` для маршрутизации `pool.*` через выделенный execution path в workflow worker (без fallback в generic драйверы).
- [ ] 1.2 Зафиксировать fail-closed поведение при отсутствии pool executor (runtime error вместо `execution_skipped` успеха).
- [ ] 1.3 Уточнить правила status projection: `published/partial_success` только при подтверждённом завершении publication-step.
- [ ] 1.4 Зафиксировать контракт internal status update (`error_code`, `error_message`, optional `error_details`) и правила его propagation в diagnostics facade.
- [ ] 1.5 Зафиксировать bridge payload-контракт с pinned binding provenance (`operation_ref`, `template_exposure_id`, `template_exposure_revision`).

## 2. Worker: poolops execution path
- [ ] 2.1 Добавить `poolops`-драйвер/адаптер и wiring в workflow engine (`OperationExecutor` dependency injection).
- [ ] 2.2 Реализовать маршрутизацию `pool.*` operation types только в `poolops` path; запретить fallback в generic drivers.
- [ ] 2.3 Реализовать fail-closed обработку misconfiguration (нет executor/adapter) с machine-readable ошибкой.
- [ ] 2.4 Реализовать bridge-контракт: internal auth, tenant propagation, bounded timeout/retry, idempotency key per step attempt.
- [ ] 2.5 Обновить worker->orchestrator client path для передачи `error_code` в `update-execution-status`.
- [ ] 2.6 Добавить в bridge request передачу `node_id` и pinned binding provenance для deterministic drift/idempotency обработки.

## 3. Orchestrator: projection hardening
- [ ] 3.1 Обновить rules в pool run projection, чтобы исключить `published` при `workflow:completed` без подтверждённого publication-step результата.
- [ ] 3.2 Убрать/пересобрать синтетические переходы `publication_step_state` из агрегатного workflow status updater.
- [ ] 3.3 Обеспечить обратную совместимость historical run-ов и стабильные diagnostics в API.
- [ ] 3.4 Реализовать staged migration для `workflow_core` historical run-ов с `publication_step_state=null` (cutoff/backfill + rollback-safe поведение).

## 4. Validation
- [ ] 4.1 Unit tests: routing `pool.*`, fail-closed при отсутствии executor, отсутствие `execution_skipped`-success для pool path.
- [ ] 4.2 Integration tests: `publication_odata` реально исполняется, создаются publication attempts/documents.
- [ ] 4.3 Regression tests: сценарий “workflow completed без публикации” не проецируется как `published`.
- [ ] 4.4 Observability tests: трассировка bridge-вызовов, retry-счётчики, fail-closed ошибки с machine-readable кодами.
- [ ] 4.5 Contract tests: `WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED` проходит по цепочке `worker -> internal API -> facade diagnostics`.
- [ ] 4.6 Migration tests: historical `workflow_core` run (до cutoff) остаётся читаемым без forced `failed`, новый run (после cutoff) fail-closed.
- [ ] 4.7 Прогнать `openspec validate add-poolops-driver-workflow-runtime-fail-closed --strict --no-interactive`.
