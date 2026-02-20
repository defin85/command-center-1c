## Context
Цель change: сделать execution-среду фактически единой для платформы (`workers + workflows`) и обеспечить операторскую наблюдаемость в `/operations`, одновременно детализировав `pool run` до атомарных workflow-шагов.

Code-first наблюдения:
- `execute_workflow` still multi-path: Go Worker / background runner / sync fallback (`orchestrator/apps/api_v2/views/workflows/templates.py:530`).
- enqueue workflow execution публикует stream message, но не создает `BatchOperation` (`orchestrator/apps/operations/services/operations_service/workflow.py:35`).
- `/operations` опирается на `BatchOperation` как primary read-model (`orchestrator/apps/api_v2/views/operations/listing.py:169`).
- worker event subscriber обновляет `BatchOperation`, и при отсутствии записи только логирует warning (`orchestrator/apps/operations/event_subscriber/handlers_worker.py:447`).
- enqueue path не фиксирует полноценную transactional границу между записью в БД и публикацией в stream; это повышает риск рассинхрона проекции.
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

Production policy фиксируется явно:
- при production execution profile локальный in-process/background fallback всегда запрещён;
- ошибка enqueue всегда возвращается клиенту как fail-closed результат;
- debug fallback допускается только вне production и только под явным feature flag, не влияющим на production semantics.

### Decision 2: Transactional outbox обязателен для workflow enqueue
Путь enqueue ДОЛЖЕН (SHALL) использовать transactional outbox, чтобы запись состояния в БД и публикация команды в stream были согласованы по commit semantics.

Гарантии:
- до commit транзакции enqueue не считается завершенным;
- rollback транзакции не оставляет «призрачный» queued state;
- outbox relay публикует команды idempotent образом и безопасен к повторной доставке.

### Decision 3: Workflow execution проецируется в `BatchOperation` как обязательный root operation record
Для каждого workflow execution enqueue создается/обновляется root `BatchOperation` (`operation_id == workflow_execution_id`) с единым metadata-контрактом (`execution_consumer`, `lane`, correlation ids).

Это позволяет использовать существующий `/operations` list/stream/timeline UX без параллельного “второго мира” observability.

Projection semantics:
- root record создаётся idempotent upsert-ом до enqueue в состоянии `pending`;
- перевод в `queued` происходит только после успешного XADD;
- при повторном enqueue того же `workflow_execution_id` создаётся не дубликат, а повторное обновление существующего root record;
- для исторических пропусков обязателен detect+repair/backfill path с алертингом.

### Decision 4: Stream split сохраняется как lane-механизм, не как отдельная runtime-модель
`commands:worker:operations` и `commands:worker:workflows` остаются допустимыми lane-ами для QoS/isolation, но должны оставаться в едином execution contract (envelope, events, telemetry, idempotency semantics).

### Decision 5: Pool run компилируется в атомарный workflow graph
Compiler должен строить nodes per edge/document action на основе:
- distribution artifact (`update-01-pool-run-full-chain-distribution`);
- document plan artifact (`add-02-pool-document-policy`).

Сценарий `Реализация/Поступление + СчетФактура` фиксируется как отдельные атомарные шаги с явными link/provenance.

### Decision 6: Root + atomic step observability должны быть коррелированы публичным контрактом
Оператор должен видеть:
- root execution в `/operations`;
- атомарные шаги с `workflow_execution_id/node_id/root_operation_id`;
- согласованные статусы/таймлайн между worker events и workflow status update.
- поля `execution_consumer` и `lane` в list/details/stream API для runtime диагностики без неявных эвристик.

### Decision 7: Трехтрековая реализация с явными зависимостями
Реализация делится на три трека:
- Track A (independent): single enqueue runtime, transactional outbox, root projection в `/operations`, lane parity.
- Track B (dependent): pool atomic graph compile на основе `distribution_artifact.v1` и `document_plan_artifact.v1`.
- Track C (dependent): интеграция diagnostics UX в `refactor-04-pools-ui-declutter` на стабилизированных полях observability contract.

Track B стартует только после готовности upstream артефактов из:
- `update-01-pool-run-full-chain-distribution`;
- `add-02-pool-document-policy`.

Track C стартует только после публикации контрактов из Track A:
- `root_operation_id`;
- `execution_consumer`;
- `lane`.

## Alternatives Considered
### A1. Оставить fallback path для “надежности”
Отклонено: это сохраняет два runtime поведения и разрушает детерминированность/операционную диагностику.

### A2. Root projection без outbox (только best-effort enqueue)
Отклонено: остаются race conditions между DB-state и stream publish, что приводит к ложным queued/missing events при ошибках транзакции.

### A3. Отдельный `/workflow-operations` UI вместо `/operations`
Отклонено: приводит к двойному NOC-интерфейсу и усложняет поддержку корреляции инцидентов.

### A4. Не детализировать pool run на атомарные шаги
Отклонено: не закрывает требование управляемой пользовательской кастомизации и selective retry на уровне документа/ребра.

## Risks / Trade-offs
- Риск: рост количества operation records и timeline events.
  - Mitigation: TTL/архивация событий, пагинация, лимиты stream подписок.
- Риск: migration для historical workflow execution без root operation record.
  - Mitigation: reconciliation/backfill job + idempotent upsert.
- Риск: операционная сложность outbox relay и monitoring lag.
  - Mitigation: metrics по outbox depth/age, alerting на stuck relay, runbook для replay.
- Риск: временный drift между existing pool runtime change-ами.
  - Mitigation: явные dependencies на `update-01-pool-run-full-chain-distribution` и `add-02-pool-document-policy`.
- Риск: refactor-04 начнёт использовать нестабилизированные observability поля.
  - Mitigation: явный blocker Track C до завершения контрактов Track A.

## Migration Plan
1. Зафиксировать spec-контракты single enqueue runtime + transactional outbox + root `BatchOperation` projection + observability fields.
2. Реализовать Track A: outbox boundary, root projection record на enqueue, queue-only workflow execute path, lane parity.
3. Обновить OpenAPI/clients и ввести backward-compatible rollout для новых observability полей.
4. Подтвердить готовность upstream артефактов (`distribution_artifact.v1`, `document_plan_artifact.v1`).
5. Реализовать Track B: atomic pool graph compile на artifacts.
6. Стартовать Track C (`refactor-04`) для финальной интеграции diagnostics UX на стабилизированном контракте.
7. Добавить reconciliation/backfill, observability parity tests и release quality gates.

## Open Questions
- Нужен ли отдельный retention профиль для atomic step timeline (по сравнению с root operation timeline), или достаточно текущих глобальных лимитов `/operations`?
- Допустим ли fallback-путь чтения старых событий без `execution_consumer/lane` в течение миграционного окна, или миграция должна быть strict cutover?
