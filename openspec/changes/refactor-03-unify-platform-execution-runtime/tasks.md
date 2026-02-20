## 0. Coordination and Sequencing
- [x] 0.1 Зафиксировать delivery tracks и порядок:
  - Track A: single enqueue runtime + transactional outbox + root `BatchOperation` projection.
  - Track B: pool atomic workflow expansion.
  - Track C: UI diagnostics integration в `refactor-04-pools-ui-declutter` на стабилизированном observability contract.
- [x] 0.2 Зафиксировать blockers:
  - для Track B: наличие `distribution_artifact.v1` и `document_plan_artifact.v1`;
  - для Track C: готовность полей `root_operation_id`, `execution_consumer`, `lane` в `/operations` list/stream.
- [x] 0.3 Добавить cross-change integration checklist и контрактные smoke tests для handoff артефактов/полей.
  - Beads graph for the sequence is tracked in epic `command-center-1c-1hd7` (`.1` ... `.28`).
  - Track B gate (MUST pass before `3.1`):
    - `update-01-pool-run-full-chain-distribution` publishes `distribution_artifact.v1` for runtime compile.
    - `add-02-pool-document-policy` publishes `document_plan_artifact.v1` with `invoice_mode` policy semantics.
  - Track C gate (MUST pass before `refactor-04` integration):
    - `/operations` contracts expose `root_operation_id`, `execution_consumer`, `lane` in list/details/stream payloads.
  - Cross-change smoke checklist:
    - Contract smoke: enqueue workflow returns fail-closed error on publish failure and does not execute fallback path.
    - Projection smoke: root `BatchOperation` appears for every workflow enqueue with `operation_id == workflow_execution_id`.
    - Lane parity smoke: worker events from each lane project the same observability fields.

## 1. Unified Runtime Contract (Single Enqueue)
- [x] 1.1 Зафиксировать canonical execution envelope для `execute_workflow` и manual operations (единые обязательные поля correlation/provenance).
- [x] 1.2 Убрать hidden fallback path в `POST /api/v2/workflows/execute-workflow/` для production execution profile (queue-only + fail-closed enqueue error, без исключений по debug-настройкам).
- [x] 1.3 Зафиксировать explicit runtime controls для non-production debug fallback с жёсткой защитой от включения в production.

## 2. Transactional Enqueue and Root `BatchOperation` Projection
- [x] 2.1 Ввести transactional outbox boundary для workflow enqueue (DB state change и stream publish без расхождения commit semantics).
- [x] 2.2 Добавить обязательное transactional создание/обновление root `BatchOperation` для workflow execution enqueue (`operation_id = workflow_execution_id`).
- [x] 2.3 Обеспечить idempotent status sync root record из worker events/internal status updates.
- [x] 2.4 Добавить reconciliation path для workflow execution без projection record (detect + repair + alert).
- [x] 2.5 Добавить backfill job для historical workflow execution без root record с idempotent upsert и SLA-мониторингом.

## 3. Pool Run Atomic Workflow Expansion
- [x] 3.1 Перевести compile `pool run` на атомарные workflow nodes из `distribution_artifact.v1` + `document_plan_artifact.v1` (Track B, после закрытия blocker'ов).
- [x] 3.2 Зафиксировать стабильные deterministic node ids (`edge/document/action`) и provenance для retry/selective replay.
- [x] 3.3 Обязать явное создание invoice-step при policy `invoice_mode=required` и fail-closed при его отсутствии.

## 4. Stream Lanes and Unified Observability
- [x] 4.1 Уточнить stream split как QoS lanes с единым execution/telemetry контрактом.
- [x] 4.2 Гарантировать, что `/operations/list`, `/operations/stream*`, timeline и фильтры покрывают workflow root + atomic steps независимо от lane.
- [x] 4.3 Добавить публичный observability contract (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`) в list/details/stream payloads.

## 5. Contracts and API
- [x] 5.1 Обновить OpenAPI контракты под single-enqueue + outbox/projection semantics (state transitions и fail-closed error contract).
- [x] 5.2 Обновить OpenAPI контракты для unified execution observability полей (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`) и фильтров `/operations`.
- [x] 5.3 Обновить generated frontend API/client types для новых/уточненных контрактов `/operations` и workflow execute path.

## 6. Tests
- [x] 6.1 Добавить backend tests на queue-only workflow execute path (enqueue failure не приводит к in-process execution).
- [x] 6.2 Добавить tests на transactional outbox semantics (успешный commit публикует событие, rollback не публикует).
- [x] 6.3 Добавить tests на projection consistency: enqueue -> queued -> completed/failed для root `BatchOperation`.
- [x] 6.4 Добавить pool runtime tests на atomic graph compile и selective retry по failed atomic nodes.
- [ ] 6.5 Добавить frontend tests на отображение unified операций (manual + workflow + pool atomic steps) в `/operations`.
- [x] 6.6 Добавить integration tests на detect+repair/backfill для workflow execution без root projection record.

## 7. Validation
- [ ] 7.1 Прогнать `openspec validate refactor-03-unify-platform-execution-runtime --strict --no-interactive`.
- [ ] 7.2 Прогнать целевые backend/worker/frontend тесты для execution и observability paths.
