## ADDED Requirements
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
