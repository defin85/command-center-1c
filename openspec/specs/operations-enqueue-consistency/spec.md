# operations-enqueue-consistency Specification

## Purpose
TBD - created by archiving change update-orchestrator-enqueue-consistency. Update Purpose after archive.
## Requirements
### Requirement: Orchestrator не обновляет статус операции в QUEUED без успешного XADD
Система ДОЛЖНА (SHALL) переводить `BatchOperation.status` в `queued` только после успешной записи сообщения в Redis Stream (XADD). Если запись в Redis не удалась, операция НЕ ДОЛЖНА (SHALL NOT) становиться `queued`.

#### Scenario: Redis недоступен → операция не становится queued
- **GIVEN** Redis недоступен или XADD завершился ошибкой
- **WHEN** пользователь (или внутренний код) инициирует enqueue операции
- **THEN** Orchestrator возвращает ошибку enqueue
- **AND** `BatchOperation.status` остаётся не-queued (например `pending`)

### Requirement: Workflow enqueue consistency MUST включать root operation projection
Система ДОЛЖНА (SHALL) применять enqueue consistency правило к workflow execution path:
- root `BatchOperation` projection record создается/обновляется до enqueue как `pending`;
- переход root record в `queued` выполняется только после успешного XADD;
- при неуспешном XADD root record НЕ ДОЛЖЕН (SHALL NOT) становиться `queued`.

Система ДОЛЖНА (SHALL) обеспечивать idempotent upsert root record для повторного enqueue одного `workflow_execution_id`.

#### Scenario: Redis недоступен при workflow enqueue
- **GIVEN** инициирован enqueue workflow execution
- **AND** XADD в Redis stream завершился ошибкой
- **WHEN** система обрабатывает результат enqueue
- **THEN** root operation projection остаётся в состоянии не-queued (`pending` или `failed` по policy)
- **AND** `/operations` не показывает ложный `queued` статус

#### Scenario: Повторный enqueue того же workflow_execution_id не создаёт дубликат root record
- **GIVEN** root operation projection уже существует для `workflow_execution_id`
- **WHEN** выполняется повторный enqueue с тем же idempotency ключом
- **THEN** система выполняет idempotent upsert существующего root record
- **AND** дублирующая запись operation в `/operations` не создаётся

### Requirement: Workflow enqueue consistency MUST использовать transactional outbox
Система ДОЛЖНА (SHALL) использовать transactional outbox для workflow enqueue, чтобы состояние root projection и публикация stream-команды были согласованы по commit semantics.

Система ДОЛЖНА (SHALL) гарантировать, что outbox relay публикует событие не более одного раза логически (idempotent delivery contract для потребителя).

#### Scenario: Commit транзакции приводит к публикации outbox команды
- **GIVEN** root projection подготовлен в транзакции и транзакция успешно зафиксирована
- **WHEN** outbox relay обрабатывает запись
- **THEN** команда enqueue публикуется в worker stream
- **AND** root projection переходит в `queued` только после подтвержденной публикации

#### Scenario: Rollback транзакции не оставляет outbox side effects
- **GIVEN** root projection и outbox запись подготовлены в транзакции
- **AND** транзакция откатывается
- **WHEN** outbox relay выполняет очередной цикл
- **THEN** enqueue команда не публикуется
- **AND** в `/operations` отсутствует ложный queued state

### Requirement: Workflow projection consistency MUST включать detect+repair/backfill для пропущенных root records
Система ДОЛЖНА (SHALL) детектировать workflow execution записи, для которых отсутствует root operation projection в `/operations`, и выполнять idempotent repair/backfill.

Система ДОЛЖНА (SHALL) публиковать alert/diagnostics событие при обнаружении такого рассинхрона, чтобы инцидент был наблюдаем оператором.

#### Scenario: Historical execution без root projection восстанавливается backfill-процедурой
- **GIVEN** в системе существует `workflow_execution_id` без root operation record
- **WHEN** запускается reconciliation/backfill процесс
- **THEN** создаётся root operation record с `operation_id = workflow_execution_id`
- **AND** запись становится доступной через `/operations` endpoints без ручного исправления

### Requirement: Workflow enqueue MUST валидировать scheduling contract для sync workload
Система ДОЛЖНА (SHALL) принимать workflow enqueue для sync workload только при валидном scheduling contract:
- `priority` из enum `p0|p1|p2|p3`;
- `role` из enum `inbound|outbound|reconcile|manual_remediation`;
- `server_affinity` не пустой;
- `deadline_at` в RFC3339 UTC и строго в будущем на момент enqueue.

Система НЕ ДОЛЖНА (SHALL NOT) публиковать enqueue-команду в stream при невалидном scheduling payload.

#### Scenario: Невалидный scheduling payload блокирует enqueue
- **GIVEN** enqueue workflow execution содержит некорректный `priority` или пустой `server_affinity`
- **WHEN** система выполняет pre-enqueue валидацию
- **THEN** возвращается ошибка валидации с machine-readable кодом
- **AND** root operation projection не переходит в `queued`
- **AND** stream-команда не публикуется

#### Scenario: `deadline_at` в прошлом блокирует enqueue
- **GIVEN** enqueue workflow execution содержит `deadline_at`, который меньше текущего UTC времени
- **WHEN** система выполняет pre-enqueue валидацию
- **THEN** возвращается ошибка `SCHEDULING_DEADLINE_INVALID`
- **AND** stream-команда не публикуется

### Requirement: Workflow enqueue outbox MUST поддерживать deferred relay и repair
Система ДОЛЖНА (SHALL) поддерживать deferred relay для `workflow_enqueue_outbox`, если inline dispatch не завершился успешно.

Система ДОЛЖНА (SHALL) обеспечивать detect+repair/backfill для зависших outbox-записей и пропущенных root projection.

Система НЕ ДОЛЖНА (SHALL NOT) переводить root operation projection в `queued` до подтверждённой публикации stream-команды.

#### Scenario: Inline dispatch падает, deferred relay завершает enqueue консистентно
- **GIVEN** root projection и outbox запись успешно зафиксированы
- **AND** inline dispatch в stream завершился ошибкой
- **WHEN** deferred relay обрабатывает pending outbox запись
- **THEN** команда публикуется в stream идемпотентно
- **AND** root projection переходит в `queued` только после подтверждённой публикации

#### Scenario: Detect+repair восстанавливает зависший enqueue
- **GIVEN** в системе есть pending outbox запись старше policy порога
- **WHEN** запускается detect+repair/backfill процедура
- **THEN** запись обрабатывается или переводится в явный `failed` с machine-readable кодом
- **AND** оператор получает диагностическое событие для follow-up

### Requirement: Workflow queue processing MUST сохранять observability scheduling полей
Система ДОЛЖНА (SHALL) сохранять `priority`, `role`, `server_affinity`, `deadline_at` в operation metadata и event/timeline payload для последующей диагностики SLA.

#### Scenario: Scheduling метаданные доступны в operations/timeline
- **GIVEN** workflow execution поставлен в очередь с валидным scheduling contract
- **WHEN** оператор запрашивает operation details или timeline события
- **THEN** response/events содержат согласованные `priority`, `role`, `server_affinity`, `deadline_at`
- **AND** значения пригодны для фильтрации backlog и latency аналитики

### Requirement: Operations read-model MUST поддерживать фильтрацию по scheduling contract
Система ДОЛЖНА (SHALL) поддерживать фильтры операций/очереди по `priority`, `role`, `server_affinity`, `deadline_state`.

#### Scenario: Оператор фильтрует очередь по scheduling полям
- **GIVEN** в очереди присутствуют sync-задачи разных ролей и affinity
- **WHEN** оператор запрашивает список операций с фильтрами `role` и `server_affinity`
- **THEN** ответ содержит только соответствующие записи
- **AND** backlog/lag аналитика согласована с теми же фильтрами

