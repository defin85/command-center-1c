## Context
В текущем workflow-core path (Go worker) operation nodes для pool runtime (`pool.prepare_input`, `pool.distribution_calculation.*`, `pool.reconciliation_report`, `pool.approval_gate`, `pool.publication_odata`) могут доходить до `completed` без фактического side effect, если не подключён `OperationExecutor`.

Фактически это даёт:
- нарушение fail-closed инварианта pool runtime;
- неисполнение `publication_odata` при формально завершённом workflow;
- риск ложного `published` в API-проекции.

## Goals
- Гарантировать исполнение `pool.*` только через domain path.
- Убрать silent-skip для pool operation nodes.
- Исключить ложный `published` при отсутствии реального publication-step результата.
- Сохранить текущую архитектуру streams и phased migration без big-bang переписывания.

## Non-Goals
- Полный перенос domain pool logic из Python в Go.
- Изменение публичных маршрутов API или потоков очередей.
- Унификация всех operation типов в новый драйвер.

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
- internal endpoint с `X-Internal-Token`/service auth;
- обязательная tenant propagation (`tenant_id`, `pool_run_id`, `workflow_execution_id`, `node_id`);
- передача pinned binding provenance (`operation_ref.binding_mode`, `template_exposure_id`, `template_exposure_revision`);
- bounded timeout и retry только для retryable ошибок (transport/5xx/429);
- идемпотентный ключ шага (`execution_id + node_id + attempt`) для защиты от дублей side effects.

### Decision 3: Fail-closed policy для pool operation nodes
Для `pool.*` шагов:
- отсутствие executor/adapter — это runtime error, не `completed`;
- fallback на generic drivers запрещён;
- workflow execution должен завершаться ошибкой с machine-readable кодом.

### Decision 4: Жёсткая проекция terminal статусов publication
`published/partial_success` должны зависеть не только от `workflow:completed`, но и от подтверждённого завершения publication-step (`publication_step_state=completed` и корректного approval контекста).

Синтетическое проставление `publication_step_state` из агрегатного `workflow status` должно быть убрано; это убирает класс ложноположительных `published`.

### Decision 5: Worker->Orchestrator статус-контракт должен переносить machine-readable `error_code`
Fail-closed результат для `pool.*` не должен деградировать до текстовой ошибки между worker и Orchestrator.

Фиксируем расширение internal status update контракта:
- `error_code` как обязательное поле для fail-closed ошибок;
- `error_message` как человекочитаемое пояснение;
- опциональный `error_details` для диагностических данных без секретов.

Это нужно для deterministic diagnostics в API и для стабильных triage/alarm правил.

### Decision 6: Projection hardening выполняется через staged migration
Нельзя одномоментно трактовать все `workflow_core + publication_step_state=null` как `failed`, иначе historical данные будут искажены.

Фиксируем staged подход:
- historical execution (до hardening cutoff) может использовать legacy fallback по `failed_targets`;
- новые execution после cutoff должны строго следовать правилу `publication_step_state=completed` для `published/partial_success`.

### Decision 7: Rollout fail-closed/poolops требует явного kill-switch
Переход должен быть управляемым по feature flag/canary с возможностью быстрого возврата к предыдущему маршруту исполнения без отката схемы данных.

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
- Переходный период с mixed deployments.
  - Mitigation: feature-flagged rollout, canary на workflow workers, регрессионные integration tests.
- Жёсткая проекция без migration окна может перевести historical `workflow_core` run-ы в ложный `failed`.
  - Mitigation: staged cutoff + migration/backfill тесты.
- Потеря `error_code` между worker и API усложнит диагностику инцидентов.
  - Mitigation: отдельный контрактный тест на propagation `WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED`.

## Migration Plan
1. Зафиксировать/реализовать status update контракт (`error_code`, `error_message`, optional `error_details`) между worker и Orchestrator.
2. Добавить `poolops` execution path и wiring в workflow engine.
3. Включить fail-closed для `pool.*` при отсутствии executor.
4. Зафиксировать и реализовать bridge-контракт (auth/tenant/pinned provenance/timeout/retry/idempotency/observability).
5. Обновить API projection rules для terminal publication статусов и убрать синтетические переходы `publication_step_state`.
6. Реализовать staged migration projection hardening для historical `workflow_core` executions (`publication_step_state=null`).
7. Прогнать интеграционные/регрессионные сценарии (включая run `500` / 3 org / создание документов).
8. Включить rollout по feature flag/canary, затем сделать default и закрыть migration window.

## Open Questions
- Нужно ли выделить отдельный `error_code` для API-проекции случая `workflow=completed`, но `publication_step_state` отсутствует/не завершён.
