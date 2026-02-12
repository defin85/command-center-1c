## ADDED Requirements
### Requirement: Pool runs MUST исполняться через workflow execution runtime
Система ДОЛЖНА (SHALL) выполнять `Pool Run` через единый workflow runtime, который отвечает за lifecycle, enqueue, retry, audit и step orchestration.

`pools` НЕ ДОЛЖЕН (SHALL NOT) иметь отдельный независимый runtime lifecycle для исполнения run-ов.

#### Scenario: Запуск pool run создаёт и запускает workflow run
- **GIVEN** пользователь инициирует запуск `/api/v2/pools/runs`
- **WHEN** система принимает валидный запрос
- **THEN** создаётся workflow run как фактическая единица исполнения
- **AND** pool run хранит reference на соответствующий workflow run

### Requirement: Pool templates MUST компилироваться в workflow-compatible execution plan
Система ДОЛЖНА (SHALL) иметь детерминированный compiler `PoolTemplate -> WorkflowTemplate/ExecutionPlan` с явным mapping шагов и входных/выходных данных.

#### Scenario: Одинаковый pool template компилируется детерминированно
- **GIVEN** одинаковые версия pool template, входные параметры и период
- **WHEN** выполняется компиляция execution plan
- **THEN** структура workflow graph и binding mapping совпадают
- **AND** runtime provenance может быть воспроизведён для диагностики

### Requirement: Pools API MUST предоставлять domain facade над workflow run
Система ДОЛЖНА (SHALL) сохранять `pools/runs*` как доменный API, но статус, retries и diagnostics ДОЛЖНЫ (SHALL) проецироваться из workflow runtime.

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
