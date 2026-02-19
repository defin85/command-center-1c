## Context
Цель change: сделать execution-среду фактически единой для платформы (`workers + workflows`) и обеспечить операторскую наблюдаемость в `/operations`, одновременно детализировав `pool run` до атомарных workflow-шагов.

Code-first наблюдения:
- `execute_workflow` still multi-path: Go Worker / background runner / sync fallback (`orchestrator/apps/api_v2/views/workflows/templates.py:530`).
- enqueue workflow execution публикует stream message, но не создает `BatchOperation` (`orchestrator/apps/operations/services/operations_service/workflow.py:35`).
- `/operations` опирается на `BatchOperation` как primary read-model (`orchestrator/apps/api_v2/views/operations/listing.py:169`).
- worker event subscriber обновляет `BatchOperation`, и при отсутствии записи только логирует warning (`orchestrator/apps/operations/event_subscriber/handlers_worker.py:447`).
- `pool run` кладет publication payload из `run_input` (`documents_by_database`), что недостаточно для атомарной детализации (`orchestrator/apps/intercompany_pools/workflow_runtime.py:399`).
- в Go workflow path executor уже заведен через `poolops`, но non-pool операции в адаптере bypass-ятся (`go-services/worker/internal/drivers/poolops/adapter.go:126`).

## Goals / Non-Goals
- Goals:
  - единый runtime contract для execution consumers;
  - `/operations` как полный операторский контур наблюдаемости выполнения;
  - pool run execution graph на уровне атомарных шагов цепочки.
- Non-Goals:
  - физическое объединение всех streams в один stream;
  - удаление `WorkflowExecution` модели/endpoint'ов;
  - добавление универсального script engine.

## Decisions
### Decision 1: Queue-only execution path как production baseline
`POST /api/v2/workflows/execute-workflow/` и pool runtime start path должны использовать queue-first semantics с fail-closed при enqueue ошибках.

Hidden fallback (background/sync execution) в production path удаляется, чтобы исключить split-brain поведение runtime.

### Decision 2: Workflow execution проецируется в `BatchOperation` как root operation record
Для каждого workflow execution enqueue создается/обновляется root operation record (`operation_id == workflow_execution_id`) с единым metadata-контрактом (`execution_consumer`, `lane`, correlation ids).

Это позволяет использовать существующий `/operations` list/stream/timeline UX без параллельного “второго мира” observability.

### Decision 3: Stream split сохраняется как lane-механизм, не как отдельная runtime-модель
`commands:worker:operations` и `commands:worker:workflows` остаются допустимыми lane-ами для QoS/isolation, но должны оставаться в едином execution contract (envelope, events, telemetry, idempotency semantics).

### Decision 4: Pool run компилируется в атомарный workflow graph
Compiler должен строить nodes per edge/document action на основе:
- distribution artifact (`update-pool-run-full-chain-distribution`);
- document plan artifact (`add-pool-document-policy`).

Сценарий `Реализация/Поступление + СчетФактура` фиксируется как отдельные атомарные шаги с явными link/provenance.

### Decision 5: Root + atomic step observability должны быть коррелированы
Оператор должен видеть:
- root execution в `/operations`;
- атомарные шаги с `workflow_execution_id/node_id/root_operation_id`;
- согласованные статусы/таймлайн между worker events и workflow status update.

## Alternatives Considered
### A1. Оставить fallback path для “надежности”
Отклонено: это сохраняет два runtime поведения и разрушает детерминированность/операционную диагностику.

### A2. Отдельный `/workflow-operations` UI вместо `/operations`
Отклонено: приводит к двойному NOC-интерфейсу и усложняет поддержку корреляции инцидентов.

### A3. Не детализировать pool run на атомарные шаги
Отклонено: не закрывает требование управляемой пользовательской кастомизации и selective retry на уровне документа/ребра.

## Risks / Trade-offs
- Риск: рост количества operation records и timeline events.
  - Mitigation: TTL/архивация событий, пагинация, лимиты stream подписок.
- Риск: migration для historical workflow execution без root operation record.
  - Mitigation: reconciliation/backfill job + idempotent upsert.
- Риск: временный drift между existing pool runtime change-ами.
  - Mitigation: явные dependencies на `update-pool-run-full-chain-distribution` и `add-pool-document-policy`.

## Migration Plan
1. Зафиксировать spec-контракты unified runtime + operations projection + atomic pool graph.
2. Ввести root projection record на enqueue.
3. Удалить hidden production fallback для execute-workflow.
4. Подключить atomic pool graph compile на artifacts.
5. Добавить reconciliation/backfill и observability parity тесты.
6. Перекрыть quality gates по OpenAPI/client parity и runtime contract tests.

## Open Questions
- Нужен ли отдельный retention профиль для atomic step timeline (по сравнению с root operation timeline), или достаточно текущих глобальных лимитов `/operations`?
