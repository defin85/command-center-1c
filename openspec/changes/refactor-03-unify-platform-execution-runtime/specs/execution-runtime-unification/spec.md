## ADDED Requirements
### Requirement: Платформа MUST использовать единый execution runtime контракт для workers и workflows
Система ДОЛЖНА (SHALL) использовать один canonical execution контракт для всех execution consumers (`operations`, `workflows`, `pools`) в queue-first модели.

Система НЕ ДОЛЖНА (SHALL NOT) использовать скрытый in-process/sync fallback в production execution path для `POST /api/v2/workflows/execute-workflow/` и связанных workflow run path.

При enqueue ошибке система ДОЛЖНА (SHALL) возвращать fail-closed ошибку и НЕ ДОЛЖНА (SHALL NOT) продолжать выполнение в альтернативном локальном runtime path.

#### Scenario: Enqueue failure не переводится в локальный sync/background execution
- **GIVEN** клиент вызывает `POST /api/v2/workflows/execute-workflow/`
- **AND** enqueue в worker stream завершается ошибкой
- **WHEN** API формирует ответ
- **THEN** возвращается fail-closed ошибка enqueue
- **AND** workflow execution не запускается через локальный background/sync fallback

### Requirement: Workflow execution MUST проецироваться в `/operations` как root operation record
Система ДОЛЖНА (SHALL) создавать/обновлять канонический operation record для workflow execution (`operation_id = workflow_execution_id`) с едиными status/timeline semantics.

Система ДОЛЖНА (SHALL) обеспечивать, что `/api/v2/operations/list-operations/`, `/api/v2/operations/get-operation/`, `/api/v2/operations/stream*` и timeline API возвращают этот root record и его progression.

#### Scenario: Workflow execution виден оператору в `/operations`
- **GIVEN** workflow execution успешно enqueue
- **WHEN** оператор открывает `/operations`
- **THEN** в списке присутствует root operation record, связанный с `workflow_execution_id`
- **AND** status/timeline record обновляются по worker events/status updates

### Requirement: Unified observability MUST сохранять корреляцию root execution и атомарных шагов
Система ДОЛЖНА (SHALL) поддерживать correlation metadata между root execution и атомарными шагами (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`).

Система ДОЛЖНА (SHALL) обеспечивать единообразную диагностику для manual operations, workflow execution и pool atomic steps в общем `/operations` read-model.

#### Scenario: Оператор трассирует инцидент от root workflow к проблемному step
- **GIVEN** root workflow execution завершился `failed`
- **WHEN** оператор открывает timeline/details в `/operations`
- **THEN** root record содержит ссылки на проблемный atomic step (`node_id`)
- **AND** machine-readable код ошибки совпадает между root и step diagnostics

### Requirement: Stream split MUST трактоваться как QoS lanes единого runtime
Система ДОЛЖНА (SHALL) трактовать разные streams (`commands:worker:operations`, `commands:worker:workflows`) как transport lanes единой runtime модели, а не как разные execution semantics.

Система ДОЛЖНА (SHALL) обеспечивать parity envelope/events/observability контрактов независимо от выбранного lane.

#### Scenario: Разные worker deployment работают по разным stream, но единый runtime-контракт сохраняется
- **GIVEN** operations и workflows обрабатываются разными deployment через разные streams
- **WHEN** операции исполняются и публикуют события статуса
- **THEN** `/operations` показывает согласованную статусную модель и telemetry для обоих lanes
- **AND** execution semantics не зависят от конкретного stream name
