# Change: Унифицировать execution runtime платформы и детализировать pool run до атомарных workflow-шагов

## Why
Сейчас execution-модель остается фрагментированной и не даёт устойчивый source-of-truth:

- `execute_workflow` в API имеет fallback на in-process/background/sync путь, то есть не всегда исполняется через единый worker runtime (`orchestrator/apps/api_v2/views/workflows/templates.py:530`).
- enqueue workflow execution публикует сообщение в `commands:worker:workflows`, но не создает обязательный root `BatchOperation`, из-за чего `/operations` не является полным source-of-truth для workflow execution (`orchestrator/apps/operations/services/operations_service/workflow.py:35`).
- обработчики worker событий обновляют только `BatchOperation`; при его отсутствии состояние workflow в `/operations` теряется (`orchestrator/apps/operations/event_subscriber/handlers_worker.py:447`).
- enqueue path не фиксирует transactional boundary между DB-записью и publish в stream (нужен единый outbox-подход), что повышает риск рассинхрона статусов.
- `pool run` уже идет через workflow runtime, но публикационный payload все еще формируется из `run_input.documents_by_database`, а не из атомарного execution-плана по цепочке (`orchestrator/apps/intercompany_pools/workflow_runtime.py:399`).

Пользовательская цель: одна execution-среда для `workers + workflows`, с полной наблюдаемостью в `/operations`, и конвертацией `pool run` в детальный набор атомарных шагов.

## What Changes
- Ввести единый platform-level execution contract для всех execution consumers (`operations`, `workflows`, `pools`) с queue-first/fail-closed semantics и без скрытого in-process fallback в production path.
- Зафиксировать обязательный transactional enqueue через outbox-паттерн (DB state + stream publish без расхождения commit semantics).
- Зафиксировать обязательную проекцию workflow execution в `/operations` как root `BatchOperation` (канонический operation record + timeline + status sync).
- Зафиксировать расширенный observability contract (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`) для `/operations` list/stream/timeline.
- Зафиксировать, что `pool run` компилируется в атомарный workflow graph по шагам доменной публикации (включая документы и связанные счет-фактуры при policy `required`), а не в coarse-grained публикацию из raw payload.
- Уточнить роль stream split: разные Redis streams остаются допустимыми как QoS lanes, но runtime/observability контракт должен быть единым.

## Impact
- Affected specs:
  - `execution-runtime-unification` (new)
  - `pool-workflow-execution-core`
  - `operations-enqueue-consistency`
  - `worker-stream-routing`
- Affected code (expected):
  - `orchestrator/apps/api_v2/views/workflows/templates.py`
  - `orchestrator/apps/operations/services/operations_service/workflow.py`
  - `orchestrator/apps/operations/event_subscriber/handlers_worker.py`
  - `orchestrator/apps/api_v2/views/operations/*`
  - `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  - `go-services/worker/internal/drivers/workflowops/*`
  - `go-services/worker/internal/drivers/poolops/*`
  - `contracts/orchestrator/openapi.yaml`
  - `frontend/src/api/queries/operations.ts`
  - `frontend/src/pages/Operations/**`
- Dependencies:
  - `update-01-pool-run-full-chain-distribution` (distribution artifact как source-of-truth).
  - `add-02-pool-document-policy` (document plan/policy для document-chain детализации).
  - `refactor-04-pools-ui-declutter` зависит от стабилизации observability contract из этого change для финальной интеграции diagnostics UX.

## Coordination with sibling changes
- Track A (platform runtime unification + transactional enqueue + `/operations` projection) реализуется первым и независимо от pool domain эволюции.
- Track B (pool atomic workflow expansion) ДОЛЖЕН (SHALL) использовать готовые артефакты:
  - `distribution_artifact.v1` из `update-01-pool-run-full-chain-distribution`;
  - `document_plan_artifact.v1` из `add-02-pool-document-policy`.
- Track C (UI diagnostics integration в `refactor-04-pools-ui-declutter`) ДОЛЖЕН (SHALL) опираться на стабилизированные поля observability contract из Track A.
- Этот change НЕ переопределяет:
  - формулы распределения и reconciliation инварианты (scope `update-01-pool-run-full-chain-distribution`);
  - policy schema/валидацию document chains (scope `add-02-pool-document-policy`).

## Non-Goals
- Не объединять физически все streams в один stream-name.
- Не удалять existing `WorkflowExecution` read API.
- Не вводить новый DSL исполнения.

## Assumptions
- Единая execution-среда означает единый runtime контракт и observability model, а не обязательный единый транспортный lane.
- `/operations` должен стать операторским entrypoint для контроля выполнения как минимум на уровне root workflow execution и атомарных шагов.
