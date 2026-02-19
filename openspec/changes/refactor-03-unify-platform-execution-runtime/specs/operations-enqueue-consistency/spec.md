## ADDED Requirements
### Requirement: Workflow enqueue consistency MUST включать root operation projection
Система ДОЛЖНА (SHALL) применять enqueue consistency правило к workflow execution path:
- root operation projection record создается/обновляется до enqueue как `pending`;
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
