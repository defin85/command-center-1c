## Context
В текущем workflow-core path (Go worker) operation nodes для pool runtime (`pool.prepare_input`, `pool.distribution_calculation.*`, `pool.reconciliation_report`, `pool.approval_gate`, `pool.publication_odata`) могут доходить до `completed` без фактического side effect, если не подключён `OperationExecutor`.

Фактически это даёт:
- нарушение fail-closed инварианта pool runtime;
- неисполнение `publication_odata` при формально завершённом workflow;
- риск ложного `published` в API-проекции.
- потерю machine-readable диагностики между worker и API;
- retry amplification из-за stacked retry (`workflowops` + HTTP client).

## Goals
- Гарантировать исполнение `pool.*` только через domain path.
- Убрать silent-skip для pool operation nodes.
- Исключить ложный `published` при отсутствии реального publication-step результата.
- Зафиксировать детерминированный bridge-контракт (path/schema/status-matrix/idempotency).
- Исключить stacked retry и определить single retry owner.
- Сохранить текущую архитектуру streams и phased migration без big-bang переписывания.

## Non-Goals
- Полный перенос domain pool logic из Python в Go.
- Изменение публичных маршрутов API или потоков очередей.
- Унификация всех operation типов в новый драйвер.
- Рефакторинг shared `odata-core` между драйверами в этом change (делается отдельно в `refactor-shared-odata-core`).

## Decisions
### Decision 1: Новый `poolops`-драйвер вместо расширения generic `odataops`
Выбран отдельный `poolops` путь, потому что `pool.*` шаги содержат доменную state-machine семантику (`approval_state`, `publication_step_state`, safe/unsafe gate), а не только CRUD/OData операции.

Почему не расширять текущий generic драйвер:
- выше blast radius для существующих `create|update|delete|query` сценариев;
- смешение доменной orchestration логики с transport-операциями;
- сложнее обеспечить независимый rollout и наблюдаемость.

### Decision 2: Bridge-исполнение через существующий domain backend контракт
`poolops` в Go worker должен делегировать исполнение в уже существующий pool domain runtime contract (Python path), а не дублировать бизнес-логику в Go в этом change.

Это даёт:
- единый source-of-truth доменной логики;
- минимальный риск drift между Python и Go реализациями;
- обратимый поэтапный rollout.

Bridge-контракт фиксируется как обязательный:
- canonical endpoint `POST /api/v2/internal/workflows/execute-pool-runtime-step` (контракт в `contracts/orchestrator-internal/openapi.yaml`);
- internal auth через `X-Internal-Token`/service auth;
- обязательная tenant propagation (`tenant_id`, `pool_run_id`, `workflow_execution_id`, `node_id`);
- передача полного pinned binding provenance (`operation_ref.alias`, `operation_ref.binding_mode`, `operation_ref.template_exposure_id`, `operation_ref.template_exposure_revision`);
- bounded timeout;
- явная status-matrix для retry classification: retryable только `transport`, `429`, `5xx`; non-retryable `400/401/404/409`;
- идемпотентный ключ шага (`workflow_execution_id + node_id + step_attempt`) для защиты от дублей side effects;
- transport retries в пределах одного `step_attempt` ДОЛЖНЫ переиспользовать тот же idempotency key;
- новый idempotency key допускается только при новом `step_attempt` (retry уже на уровне workflow node semantics).

### Decision 3: Single retry owner для bridge-вызовов
Повторные попытки для bridge-вызовов и status update должны выполняться только в одном слое.

Фиксируем:
- `workflowops` handler не должен делать внешний retry-loop поверх клиента с уже встроенным retry;
- retry policy принадлежит транспортному слою bridge/status-update клиента (bounded backoff + jitter);
- telemetry должна фиксировать attempt count и признак resend attempt из единственного retry-owner.

### Decision 4: Fail-closed policy для pool operation nodes
Для `pool.*` шагов:
- отсутствие executor/adapter — это runtime error, не `completed`;
- fallback на generic drivers запрещён;
- workflow execution должен завершаться ошибкой с machine-readable кодом.

### Decision 5: Жёсткая проекция terminal статусов publication
`published/partial_success` должны зависеть не только от `workflow:completed`, но и от подтверждённого завершения publication-step (`publication_step_state=completed` и корректного approval контекста).

Синтетическое проставление `publication_step_state` из агрегатного `workflow status` должно быть убрано; это убирает класс ложноположительных `published`.

### Decision 6: Worker->Orchestrator статус-контракт должен переносить machine-readable `error_code`
Fail-closed результат для `pool.*` не должен деградировать до текстовой ошибки между worker и Orchestrator.

Фиксируем расширение internal status update контракта:
- `error_code` как обязательное поле для fail-closed ошибок;
- `error_message` как человекочитаемое пояснение;
- опциональный `error_details` для диагностических данных без секретов.

Фиксируем persistence для structured diagnostics:
- `WorkflowExecution` хранит `error_code` и `error_details` как source-of-truth для post-mortem и facade-projection;
- internal serializer/view принимают и валидируют `error_code`/`error_details` без потери при сохранении.

Фиксируем также mapping в facade:
- internal `error_code` проецируется наружу в Problem Details поле `code`;
- для кейса `workflow=completed` + `publication_step_state!=completed` используется стабильный `code=POOL_PUBLICATION_STEP_INCOMPLETE`.

### Decision 7: Projection hardening выполняется через staged migration и явный cutoff source
Нельзя одномоментно трактовать все `workflow_core + publication_step_state=null` как `failed`, иначе historical данные будут искажены.

Фиксируем staged подход:
- cutoff source: runtime setting `pools.projection.publication_hardening_cutoff_utc` (RFC3339 UTC);
- timestamp для сравнения: `projection_timestamp=coalesce(workflow_execution.started_at, workflow_execution.created_at, pool_run.created_at)`;
- historical execution (до hardening cutoff) может использовать legacy fallback по `failed_targets`;
- новые execution после cutoff должны строго следовать правилу `publication_step_state=completed` для `published/partial_success`.

### Decision 8: Go workflow runtime model обязан сохранять `operation_ref` end-to-end
Текущая Go DAG-модель не гарантирует проброс полного `operation_ref` (`binding_mode` и pinned provenance) в execution path.

Фиксируем:
- `operation_ref` должен сохраняться в runtime model operation-node;
- bridge payload должен включать `operation_ref` без деградации до `template_id`-only;
- fail-closed проверки pinned binding должны использовать именно `operation_ref`, а не fallback alias semantics.

### Decision 9: Rollout fail-closed/poolops требует явного kill-switch
Переход должен быть управляемым по feature flag/canary с возможностью быстрого отключения `poolops` маршрута без отката схемы данных.

Минимальные guardrails:
- feature flag для включения `poolops` маршрута;
- canary rollout по части workflow workers;
- kill-switch для немедленного отключения `poolops` маршрута без data rollback;
- отключение `poolops` через kill-switch НЕ ДОЛЖНО возвращать `pool.*` в silent-success маршрут (`execution_skipped=true` + `completed`);
- при отключённом `poolops` для `pool.*` сохраняется fail-closed поведение с machine-readable кодом;
- rollout controls для `poolops` routing и projection hardening должны быть независимыми (раздельные runtime controls).

### Decision 10: Reuse OData transport делается отдельным change
Транспортная консолидация между `poolops` и `odataops` не включается в этот change и реализуется в `refactor-shared-odata-core`.

Этот change использует текущий transport слой и фиксирует только fail-closed/runtime/projection контракты.

## Alternatives Considered
### A1. Расширить `odataops`/generic драйвер под `pool.*`
Отклонено: высокий риск регрессий, размывание ответственности драйверов, сложнее тестировать и откатывать.

### A2. Сразу переписать pool domain steps в Go
Отклонено для этого change: слишком широкий объём, высокий migration risk и дублирование логики на переходном этапе.

## Risks / Trade-offs
- Дополнительный hop между Go worker и Orchestrator domain runtime увеличивает latency.
  - Mitigation: таймауты, retry policy, метрики длительности per-step.
- Неполная идемпотентность при retry может дублировать side effects.
  - Mitigation: сохранить и проверить existing external identity/idempotency contract публикации.
- Stacked retry может создавать лишнюю нагрузку и delayed failover.
  - Mitigation: зафиксировать single retry owner и контрактный тест на отсутствие retry amplification.
- Переходный период с mixed deployments.
  - Mitigation: feature-flagged rollout, canary на workflow workers, регрессионные integration tests.
- Kill-switch, возвращающий legacy маршрут, может нарушить fail-closed инвариант.
  - Mitigation: kill-switch отключает только `poolops` routing и ведёт в fail-closed guard path, без legacy silent-success fallback.
- Жёсткая проекция без migration окна может перевести historical `workflow_core` run-ы в ложный `failed`.
  - Mitigation: staged cutoff + migration/backfill тесты.
- Потеря `error_code` между worker и API усложнит диагностику инцидентов.
  - Mitigation: отдельный контрактный тест на propagation `WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED`.

## Migration Plan
1. Зафиксировать в internal OpenAPI canonical bridge endpoint и status update contract (`error_code`, `error_message`, optional `error_details`), включая семантику `step_attempt`/transport retries для idempotency key.
2. Добавить `poolops` execution path и wiring в workflow engine.
3. Включить fail-closed для `pool.*` при отсутствии executor/adapter.
4. Убрать stacked retry: оставить единый retry owner для bridge/status update.
5. Обновить Go workflow runtime model для обязательного проброса `operation_ref`.
6. Реализовать persistence structured diagnostics в `WorkflowExecution` (`error_code`, `error_details`) и прокинуть в facade.
7. Обновить API projection rules и убрать синтетические переходы `publication_step_state`.
8. Ввести runtime setting cutoff и timestamp-формулу для staged projection hardening.
9. Пробросить machine-readable error codes до facade (`code`), включая `POOL_PUBLICATION_STEP_INCOMPLETE`.
10. Включить rollout по feature flag/canary и kill-switch в fail-closed режиме (без legacy silent-success fallback), затем сделать default и закрыть migration window.
11. Прогнать контрактные/интеграционные/регрессионные сценарии (включая run `500` / 3 org / создание документов).
