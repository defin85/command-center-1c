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
- Сконцентрировать OData transport-логику в одном переиспользуемом слое для `poolops` и `odataops`.
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

### Decision 3: Fail-closed policy для pool operation nodes
Для `pool.*` шагов:
- отсутствие executor/adapter — это runtime error, не `completed`;
- fallback на generic drivers запрещён;
- workflow execution должен завершаться ошибкой с machine-readable кодом.

### Decision 4: Жёсткая проекция terminal статусов publication
`published/partial_success` должны зависеть не только от `workflow:completed`, но и от подтверждённого завершения publication-step (`publication_step_state=completed` и корректного approval контекста).

Синтетическое проставление `publication_step_state` из агрегатного `workflow status` должно быть убрано; это убирает класс ложноположительных `published`.

### Decision 5: Общий `odata-core` как transport shared-layer
После стабилизации этапа с `poolops` вводится общий слой `odata-core`, который инкапсулирует:
- управление OData-сессией и auth;
- retry/backoff policy;
- error mapping и нормализацию диагностики;
- helpers для batch/upsert/posting вызовов.

`poolops` и `odataops` используют этот слой, но сохраняют раздельную доменную ответственность.

## Alternatives Considered
### A1. Расширить `odataops`/generic драйвер под `pool.*`
Отклонено: высокий риск регрессий, размывание ответственности драйверов, сложнее тестировать и откатывать.

### A2. Сразу переписать pool domain steps в Go
Отклонено для этого change: слишком широкий объём, высокий migration risk и дублирование логики на переходном этапе.

### A3. Оставить `poolops` и `odataops` с дублированным OData transport-кодом
Отклонено: растёт техдолг, сложнее поддерживать одинаковые retry/error semantics и фиксы протокольных дефектов.

## Risks / Trade-offs
- Дополнительный hop между Go worker и Orchestrator domain runtime увеличивает latency.
  - Mitigation: таймауты, retry policy, метрики длительности per-step.
- Неполная идемпотентность при retry может дублировать side effects.
  - Mitigation: сохранить и проверить existing external identity/idempotency contract публикации.
- Переходный период с mixed deployments.
  - Mitigation: feature-flagged rollout, canary на workflow workers, регрессионные integration tests.
- Неполная консолидация `odata-core` может привести к частичному дублированию.
  - Mitigation: миграция в два шага (сначала `poolops`, затем `odataops`) с обязательным удалением legacy transport-хелперов.

## Migration Plan
1. Добавить `poolops` execution path и wiring в workflow engine.
2. Включить fail-closed для `pool.*` при отсутствии executor.
3. Обновить API projection rules для terminal publication статусов.
4. Убрать синтетические переходы `publication_step_state` из агрегатного `workflow status` updater.
5. Прогнать интеграционные сценарии (включая run `500` / 3 org / создание документов).
6. Ввести shared `odata-core` и переключить `poolops(publication_odata)` на него.
7. Переключить `odataops` на shared `odata-core` и удалить дублирующие transport-компоненты.
8. Включить rollout по feature flag/canary и затем сделать default.

## Open Questions
- Нужен ли отдельный внутренний endpoint для `poolops` bridge-вызова, или используется существующий internal workflow/domain execution endpoint.
- Нужен ли отдельный error-code для проекции “workflow completed без publication-step результата” в API diagnostics.
- Нужно ли фиксировать единый compatibility contract для `odata-core` (например, matrix по версиям 1С/OData) в отдельной спецификации.
