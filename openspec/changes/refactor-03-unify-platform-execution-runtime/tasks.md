## 0. Coordination and Sequencing
- [ ] 0.1 Зафиксировать delivery tracks и порядок:
  - Track A: single enqueue runtime + transactional outbox + root `BatchOperation` projection.
  - Track B: pool atomic workflow expansion.
  - Track C: UI diagnostics integration в `refactor-04-pools-ui-declutter` на стабилизированном observability contract.
- [ ] 0.2 Зафиксировать blockers:
  - для Track B: наличие `distribution_artifact.v1` и `document_plan_artifact.v1`;
  - для Track C: готовность полей `root_operation_id`, `execution_consumer`, `lane` в `/operations` list/stream.
- [ ] 0.3 Добавить cross-change integration checklist и контрактные smoke tests для handoff артефактов/полей.

## 1. Unified Runtime Contract (Single Enqueue)
- [ ] 1.1 Зафиксировать canonical execution envelope для `execute_workflow` и manual operations (единые обязательные поля correlation/provenance).
- [ ] 1.2 Убрать hidden fallback path в `POST /api/v2/workflows/execute-workflow/` для production execution profile (queue-only + fail-closed enqueue error, без исключений по debug-настройкам).
- [ ] 1.3 Зафиксировать explicit runtime controls для non-production debug fallback с жёсткой защитой от включения в production.

## 2. Transactional Enqueue and Root `BatchOperation` Projection
- [ ] 2.1 Ввести transactional outbox boundary для workflow enqueue (DB state change и stream publish без расхождения commit semantics).
- [ ] 2.2 Добавить обязательное transactional создание/обновление root `BatchOperation` для workflow execution enqueue (`operation_id = workflow_execution_id`).
- [ ] 2.3 Обеспечить idempotent status sync root record из worker events/internal status updates.
- [ ] 2.4 Добавить reconciliation path для workflow execution без projection record (detect + repair + alert).
- [ ] 2.5 Добавить backfill job для historical workflow execution без root record с idempotent upsert и SLA-мониторингом.

## 3. Pool Run Atomic Workflow Expansion
- [ ] 3.1 Перевести compile `pool run` на атомарные workflow nodes из `distribution_artifact.v1` + `document_plan_artifact.v1` (Track B, после закрытия blocker'ов).
- [ ] 3.2 Зафиксировать стабильные deterministic node ids (`edge/document/action`) и provenance для retry/selective replay.
- [ ] 3.3 Обязать явное создание invoice-step при policy `invoice_mode=required` и fail-closed при его отсутствии.

## 4. Stream Lanes and Unified Observability
- [ ] 4.1 Уточнить stream split как QoS lanes с единым execution/telemetry контрактом.
- [ ] 4.2 Гарантировать, что `/operations/list`, `/operations/stream*`, timeline и фильтры покрывают workflow root + atomic steps независимо от lane.
- [ ] 4.3 Добавить публичный observability contract (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`) в list/details/stream payloads.

## 5. Contracts and API
- [ ] 5.1 Обновить OpenAPI контракты под single-enqueue + outbox/projection semantics (state transitions и fail-closed error contract).
- [ ] 5.2 Обновить OpenAPI контракты для unified execution observability полей (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`) и фильтров `/operations`.
- [ ] 5.3 Обновить generated frontend API/client types для новых/уточненных контрактов `/operations` и workflow execute path.

## 6. Tests
- [ ] 6.1 Добавить backend tests на queue-only workflow execute path (enqueue failure не приводит к in-process execution).
- [ ] 6.2 Добавить tests на transactional outbox semantics (успешный commit публикует событие, rollback не публикует).
- [ ] 6.3 Добавить tests на projection consistency: enqueue -> queued -> completed/failed для root `BatchOperation`.
- [ ] 6.4 Добавить pool runtime tests на atomic graph compile и selective retry по failed atomic nodes.
- [ ] 6.5 Добавить frontend tests на отображение unified операций (manual + workflow + pool atomic steps) в `/operations`.
- [ ] 6.6 Добавить integration tests на detect+repair/backfill для workflow execution без root projection record.

## 7. Validation
- [ ] 7.1 Прогнать `openspec validate refactor-03-unify-platform-execution-runtime --strict --no-interactive`.
- [ ] 7.2 Прогнать целевые backend/worker/frontend тесты для execution и observability paths.
