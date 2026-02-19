## 0. Coordination and Sequencing
- [ ] 0.1 Зафиксировать delivery tracks:
  - Track A: platform runtime unification + `/operations` projection.
  - Track B: pool atomic workflow expansion.
- [ ] 0.2 Зафиксировать blocker для Track B: наличие `distribution_artifact.v1` и `document_plan_artifact.v1` из sibling change-ов.
- [ ] 0.3 Добавить cross-change integration checklist и контрактные smoke tests для handoff артефактов.

## 1. Unified Runtime Contract
- [ ] 1.1 Зафиксировать canonical execution envelope для `execute_workflow` и manual operations (единые обязательные поля correlation/provenance).
- [ ] 1.2 Убрать hidden fallback path в `POST /api/v2/workflows/execute-workflow/` для production execution profile (queue-only + fail-closed enqueue error).
- [ ] 1.3 Зафиксировать explicit runtime controls для non-production debug fallback, чтобы он не смешивался с production semantics.

## 2. Workflow Projection в `/operations`
- [ ] 2.1 Добавить transactional создание/обновление root operation record для workflow execution enqueue (`operation_id = workflow_execution_id`).
- [ ] 2.2 Обеспечить idempotent status sync root record из worker events/internal status updates.
- [ ] 2.3 Добавить reconciliation path для workflow execution без projection record (detect + repair + alert).

## 3. Pool Run Atomic Workflow Expansion
- [ ] 3.1 Перевести compile `pool run` на атомарные workflow nodes из `distribution_artifact.v1` + `document_plan_artifact.v1` (Track B, после закрытия blocker'ов).
- [ ] 3.2 Зафиксировать стабильные deterministic node ids (`edge/document/action`) и provenance для retry/selective replay.
- [ ] 3.3 Обязать явное создание invoice-step при policy `invoice_mode=required` и fail-closed при его отсутствии.

## 4. Stream Lanes and Unified Observability
- [ ] 4.1 Уточнить stream split как QoS lanes с единым execution/telemetry контрактом.
- [ ] 4.2 Гарантировать, что `/operations/list`, `/operations/stream*`, timeline и фильтры покрывают workflow root + atomic steps независимо от lane.

## 5. Contracts and API
- [ ] 5.1 Обновить OpenAPI контракты для unified execution observability полей (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`).
- [ ] 5.2 Обновить generated frontend API/client types для новых/уточненных контрактов `/operations` и workflow execute path.

## 6. Tests
- [ ] 6.1 Добавить backend tests на queue-only workflow execute path (enqueue failure не приводит к in-process execution).
- [ ] 6.2 Добавить tests на projection consistency: enqueue -> queued -> completed/failed для workflow root operation record.
- [ ] 6.3 Добавить pool runtime tests на atomic graph compile и selective retry по failed atomic nodes.
- [ ] 6.4 Добавить frontend tests на отображение unified операций (manual + workflow + pool atomic steps) в `/operations`.

## 7. Validation
- [ ] 7.1 Прогнать `openspec validate refactor-03-unify-platform-execution-runtime --strict --no-interactive`.
- [ ] 7.2 Прогнать целевые backend/worker/frontend тесты для execution и observability paths.
