## ADDED Requirements
### Requirement: Pool runs MUST исполняться через workflow execution runtime
Система ДОЛЖНА (SHALL) выполнять `Pool Run` через единый workflow runtime, который отвечает за lifecycle, enqueue, retry, audit и step orchestration.

`pools` НЕ ДОЛЖЕН (SHALL NOT) иметь отдельный независимый runtime lifecycle для исполнения run-ов.

#### Scenario: Запуск pool run создаёт и запускает workflow run
- **GIVEN** пользователь инициирует запуск `/api/v2/pools/runs`
- **WHEN** система принимает валидный запрос
- **THEN** создаётся workflow run как фактическая единица исполнения
- **AND** pool run хранит reference на соответствующий workflow run

### Requirement: Pool status projection MUST быть канонической и детерминированной
Система ДОЛЖНА (SHALL) использовать единый mapping статусов между workflow runtime и pools facade:
- `pool:draft` — только до создания workflow run;
- `workflow:pending -> pool:validated`;
- `workflow:running -> pool:publishing`;
- `workflow:completed + failed_targets=0 -> pool:published`;
- `workflow:completed + failed_targets>0 -> pool:partial_success`;
- `workflow:failed|cancelled -> pool:failed`.

#### Scenario: Завершение workflow с failed targets даёт partial_success
- **GIVEN** workflow run завершён со статусом `completed`
- **AND** publication summary содержит failed targets
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `partial_success`
- **AND** в ответе остаётся ссылка на исходный workflow run

### Requirement: Tenant boundary MUST сохраняться между pool и workflow run
Система ДОЛЖНА (SHALL) обеспечивать tenant-изоляцию при запуске, чтении и retry:
- `pool_run.tenant_id` и `workflow_execution.tenant_id` обязаны совпадать;
- доступ к связанному workflow run из другого tenant-контекста НЕ ДОЛЖЕН (SHALL NOT) быть возможен.

#### Scenario: Cross-tenant доступ к workflow provenance отклоняется
- **GIVEN** pool run создан в tenant `A`
- **WHEN** пользователь tenant `B` запрашивает детали этого run
- **THEN** система отклоняет запрос как недоступный в текущем tenant context
- **AND** данные workflow provenance не раскрываются

### Requirement: Pool templates MUST компилироваться в workflow-compatible execution plan
Система ДОЛЖНА (SHALL) иметь детерминированный compiler `PoolTemplate -> WorkflowTemplate/ExecutionPlan` с явным mapping шагов и входных/выходных данных.

#### Scenario: Одинаковый pool template компилируется детерминированно
- **GIVEN** одинаковые версия pool template, входные параметры и период
- **WHEN** выполняется компиляция execution plan
- **THEN** структура workflow graph и binding mapping совпадают
- **AND** runtime provenance может быть воспроизведён для диагностики

### Requirement: Pools API MUST предоставлять domain facade над workflow run
Система ДОЛЖНА (SHALL) сохранять `pools/runs*` как доменный API, но статус, retries и diagnostics ДОЛЖНЫ (SHALL) проецироваться из workflow runtime.

Ответы facade ДОЛЖНЫ (SHALL) содержать provenance block минимум с полями:
- `workflow_run_id`,
- `workflow_status`,
- `execution_backend`,
- `retry_chain` (или эквивалент ссылки на цепочку retry).

#### Scenario: Pool details отражает workflow provenance
- **GIVEN** pool run связан с workflow run
- **WHEN** клиент запрашивает детали run
- **THEN** ответ содержит pool-доменные поля
- **AND** включает workflow provenance/diagnostics, достаточные для оператора

### Requirement: OData publication MUST исполняться как workflow step adapter
Система ДОЛЖНА (SHALL) вызывать publication service (OData) как шаг workflow execution graph, а не как отдельный orchestrator runtime.

#### Scenario: Ошибка публикации обрабатывается политикой retry workflow
- **GIVEN** шаг публикации в OData завершился транспортной ошибкой
- **WHEN** workflow runtime применяет retry policy
- **THEN** повторяются только failed step-attempts
- **AND** статусы pool run и workflow run остаются согласованными

### Requirement: Publication retry contract MUST быть единым для pools и workflow runtime
Система ДОЛЖНА (SHALL) поддерживать доменный контракт `max_attempts_total=5` для публикации в OData.

Система ДОЛЖНА (SHALL) исполнять retry endpoint `POST /pools/runs/{run_id}/retry` только для failed subset, не дублируя успешные цели.

#### Scenario: Retry повторно исполняет только failed subset
- **GIVEN** pool run имеет `partial_success` и набор failed targets
- **WHEN** клиент вызывает retry endpoint
- **THEN** система создаёт/запускает workflow execution только для failed subset
- **AND** успешные публикации из предыдущих попыток не повторяются

### Requirement: Queueing contract MUST быть фиксирован для phase 1
Система ДОЛЖНА (SHALL) отправлять workflow execution для pools в существующий workflow stream `commands:worker:workflows` с приоритетом `normal` по умолчанию.

Система НЕ ДОЛЖНА (SHALL NOT) вводить отдельный SLA/priority lane для pools в рамках этого change.

#### Scenario: Pool run enqueue использует workflow stream phase 1
- **WHEN** запускается pool run через unified execution core
- **THEN** enqueue выполняется в workflow stream `commands:worker:workflows`
- **AND** execution config использует приоритет `normal`, если явно не задано иначе в будущем extension

### Requirement: Migration MUST сохранять historical runs и идемпотентность
Система ДОЛЖНА (SHALL) обеспечить миграцию/совместимость, при которой historical pool runs остаются читаемыми, а доменный idempotency key продолжает предотвращать дубли исполнения.

#### Scenario: Historical run читается после включения unified execution
- **GIVEN** run был создан до перевода исполнения на workflow runtime
- **WHEN** оператор открывает run details после релиза
- **THEN** система возвращает совместимое представление run
- **AND** audit/provenance остаются доступными

### Requirement: Workflows decommission MUST быть запрещён до полной миграции consumers
Система НЕ ДОЛЖНА (SHALL NOT) удалять `workflows` runtime до подтверждённой миграции всех потребителей execution-core (включая pools) на общий контракт исполнения.

#### Scenario: Попытка удаления workflows блокируется preflight-проверкой
- **GIVEN** не все execution consumers мигрированы на unified execution core
- **WHEN** запускается decommission plan для workflows
- **THEN** preflight проверка помечает план как `No-Go`
- **AND** удаление runtime не выполняется
