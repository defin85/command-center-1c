# execution-runtime-unification Specification

## Purpose
TBD - created by archiving change refactor-03-unify-platform-execution-runtime. Update Purpose after archive.
## Requirements
### Requirement: Платформа MUST использовать единый execution runtime контракт для workers и workflows
Система ДОЛЖНА (SHALL) использовать один canonical execution контракт для всех execution consumers (`operations`, `workflows`, `pools`) в queue-first модели.

Система НЕ ДОЛЖНА (SHALL NOT) использовать скрытый in-process/sync fallback в production execution path для `POST /api/v2/workflows/execute-workflow/` и связанных workflow run path.

При enqueue ошибке система ДОЛЖНА (SHALL) возвращать fail-closed ошибку и НЕ ДОЛЖНА (SHALL NOT) продолжать выполнение в альтернативном локальном runtime path.

Система ДОЛЖНА (SHALL) принудительно отключать локальный fallback при production profile даже при наличии debug-настроек, чтобы избежать расхождения runtime semantics между окружениями.

#### Scenario: Enqueue failure не переводится в локальный sync/background execution
- **GIVEN** клиент вызывает `POST /api/v2/workflows/execute-workflow/`
- **AND** enqueue в worker stream завершается ошибкой
- **WHEN** API формирует ответ
- **THEN** возвращается fail-closed ошибка enqueue
- **AND** workflow execution не запускается через локальный background/sync fallback

#### Scenario: Production profile игнорирует debug fallback и остаётся queue-only
- **GIVEN** система работает в production profile
- **AND** включён debug-флаг локального fallback
- **AND** enqueue в worker stream завершается ошибкой
- **WHEN** API обрабатывает запрос execution
- **THEN** локальный fallback не используется
- **AND** клиент получает fail-closed enqueue error

### Requirement: Workflow enqueue MUST использовать transactional outbox как canonical delivery boundary
Система ДОЛЖНА (SHALL) использовать transactional outbox для workflow enqueue, чтобы запись состояния в БД и публикация команды в stream были согласованы по commit semantics.

Система НЕ ДОЛЖНА (SHALL NOT) публиковать enqueue-команду из транзакции, которая в итоге не была зафиксирована.

#### Scenario: Rollback транзакции не приводит к публикации enqueue команды
- **GIVEN** создан execution context и root record в рамках транзакции
- **AND** до commit возникает ошибка, вызывающая rollback
- **WHEN** обработка завершается
- **THEN** workflow enqueue команда не публикуется в worker stream
- **AND** `/operations` не показывает ложный queued state для этого execution

### Requirement: Workflow execution MUST проецироваться в `/operations` как root `BatchOperation`
Система ДОЛЖНА (SHALL) создавать/обновлять канонический root `BatchOperation` для workflow execution (`operation_id = workflow_execution_id`) с едиными status/timeline semantics.

Система ДОЛЖНА (SHALL) обеспечивать, что `/api/v2/operations/list-operations/`, `/api/v2/operations/get-operation/`, `/api/v2/operations/stream*` и timeline API возвращают этот root record и его progression.

Система ДОЛЖНА (SHALL) выполнять idempotent upsert root record для повторных enqueue и не создавать duplicate records для одного `workflow_execution_id`.

#### Scenario: Workflow execution виден оператору в `/operations`
- **GIVEN** workflow execution успешно enqueue
- **WHEN** оператор открывает `/operations`
- **THEN** в списке присутствует root operation record, связанный с `workflow_execution_id`
- **AND** status/timeline record обновляются по worker events/status updates

#### Scenario: Повторный enqueue не создаёт duplicate root operation
- **GIVEN** root operation record уже существует для `workflow_execution_id`
- **WHEN** происходит повторный enqueue того же execution
- **THEN** обновляется существующий root record
- **AND** новый duplicate operation record не создаётся

### Requirement: Unified observability MUST сохранять корреляцию root execution и атомарных шагов
Система ДОЛЖНА (SHALL) поддерживать correlation metadata между root execution и атомарными шагами (`workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane`).

Система ДОЛЖНА (SHALL) обеспечивать единообразную диагностику для manual operations, workflow execution и pool atomic steps в общем `/operations` read-model и в stream API.

#### Scenario: Оператор трассирует инцидент от root workflow к проблемному step
- **GIVEN** root workflow execution завершился `failed`
- **WHEN** оператор открывает timeline/details в `/operations`
- **THEN** root record содержит ссылки на проблемный atomic step (`node_id`)
- **AND** machine-readable код ошибки совпадает между root и step diagnostics

#### Scenario: API отдает observability поля одинаково в list и stream
- **GIVEN** workflow execution и его atomic nodes публикуют lifecycle события
- **WHEN** оператор использует `/operations/list` и `/operations/stream*`
- **THEN** поля `workflow_execution_id`, `node_id`, `root_operation_id`, `execution_consumer`, `lane` доступны в обоих каналах
- **AND** для клиента не требуется lane-specific ветвление логики разбора

### Requirement: Stream split MUST трактоваться как QoS lanes единого runtime
Система ДОЛЖНА (SHALL) трактовать разные streams (`commands:worker:operations`, `commands:worker:workflows`) как transport lanes единой runtime модели, а не как разные execution semantics.

Система ДОЛЖНА (SHALL) обеспечивать parity envelope/events/observability контрактов независимо от выбранного lane.

#### Scenario: Разные worker deployment работают по разным stream, но единый runtime-контракт сохраняется
- **GIVEN** operations и workflows обрабатываются разными deployment через разные streams
- **WHEN** операции исполняются и публикуют события статуса
- **THEN** `/operations` показывает согласованную статусную модель и telemetry для обоих lanes
- **AND** execution semantics не зависят от конкретного stream name

### Requirement: `/operations` MUST использовать task-first platform workspace composition
Система ДОЛЖНА (SHALL) реализовать `/operations` как canonical operational workspace поверх platform layer, где:
- catalog root `BatchOperation` records является primary entry point;
- selected operation detail, timeline и operator actions образуют устойчивый secondary context;
- list/filter, inspect, cancel/action и timeline flows разделены по операторскому намерению, а не свалены в одно page-level полотно;
- selected operation context и active view сохраняются в URL и восстанавливаются после reload/back-forward.

Primary inspect flow НЕ ДОЛЖЕН (SHALL NOT) зависеть от raw full-page modal как единственного пути просмотра детали. На узких viewport detail/timeline ДОЛЖНЫ (SHALL) открываться через mobile-safe secondary surface (`Drawer`, panel или эквивалентный route/state fallback) без page-wide horizontal overflow.

#### Scenario: Выбранная операция восстанавливается из URL без повторного ручного выбора
- **GIVEN** оператор открывает `/operations` с query state выбранной root operation
- **WHEN** страница загружается заново или пользователь возвращается через browser back/forward
- **THEN** UI восстанавливает selected operation и active inspect context
- **AND** оператору не нужно заново искать ту же запись в catalog

#### Scenario: Узкий viewport сохраняет inspect flow без монолитного canvas
- **GIVEN** оператор работает с `/operations` на narrow viewport
- **WHEN** он открывает detail или timeline выбранной операции
- **THEN** secondary context открывается в mobile-safe fallback surface
- **AND** основной list/action flow остаётся доступным без page-wide horizontal scroll

