## ADDED Requirements
### Requirement: Pools facade API contract MUST быть синхронизирован с OpenAPI source-of-truth
Система ДОЛЖНА (SHALL) поддерживать `contracts/orchestrator/openapi.yaml` в полном соответствии с фактическим runtime API для `/api/v2/pools/runs*`.

Контракт ДОЛЖЕН (SHALL) включать:
- `POST /api/v2/pools/runs/{run_id}/confirm-publication/`;
- `POST /api/v2/pools/runs/{run_id}/abort-publication/`;
- точные response-коды safe-команд (`400`, `200`, `202`, `404`, `409`);
- schema `PoolRun` и provenance поля, возвращаемые runtime (`status_reason`, `workflow_execution_id`, `workflow_status`, `approval_state`, `publication_step_state`, `terminal_reason`, `execution_backend`, `provenance.retry_chain`);
- schema `PoolPublicationAttempt` с canonical diagnostics полями (`payload_summary`, `http_error|transport_error`, `domain_error_code`, `domain_error_message`, `attempt_timestamp`).

Drift между runtime API и OpenAPI контрактом ДОЛЖЕН (SHALL) блокировать релиз как quality gate.

#### Scenario: Safe-команды доступны в OpenAPI с каноническими ответами
- **GIVEN** runtime поддерживает safe-команды публикации
- **WHEN** генерируется/проверяется `contracts/orchestrator/openapi.yaml`
- **THEN** контракт содержит endpoint-ы `confirm-publication` и `abort-publication`
- **AND** response-коды и conflict payload совпадают с runtime contract

#### Scenario: Drift контрактов блокирует CI
- **GIVEN** runtime сериализатор `PoolRun` расширен новыми полями
- **WHEN** OpenAPI контракт не обновлён
- **THEN** contract parity проверка завершается ошибкой
- **AND** релиз помечается как `No-Go`

#### Scenario: Drift между OpenAPI и generated client блокирует CI
- **GIVEN** `contracts/orchestrator/openapi.yaml` изменён для `/api/v2/pools/runs*`
- **WHEN** `frontend/src/api/generated/**` не синхронизирован с новым контрактом
- **THEN** parity проверка generated client завершается ошибкой
- **AND** релиз помечается как `No-Go`

## MODIFIED Requirements
### Requirement: Pools API MUST предоставлять domain facade над workflow run
Система ДОЛЖНА (SHALL) сохранять `pools/runs*` как доменный API, но статус, retries и diagnostics ДОЛЖНЫ (SHALL) проецироваться из workflow runtime.

Ответы facade ДОЛЖНЫ (SHALL) содержать provenance block минимум с полями:
- `workflow_run_id` (root execution chain id),
- `workflow_status` (статус active attempt),
- `approval_state` (runtime approval phase; nullable для legacy),
- `terminal_reason` (nullable; обязателен для terminal unified execution),
- `execution_backend`,
- `retry_chain`.

Для unified execution `retry_chain` ДОЛЖЕН (SHALL) быть массивом объектов lineage со структурой:
- `workflow_run_id`,
- `parent_workflow_run_id` (nullable для initial attempt),
- `attempt_number`,
- `attempt_kind` (`initial|retry`),
- `status`.

Для unified execution `retry_chain` ДОЛЖЕН (SHALL) включать минимум initial attempt; `workflow_run_id` на верхнем уровне ДОЛЖЕН (SHALL) ссылаться на root attempt, а `workflow_status` ДОЛЖЕН (SHALL) отражать active attempt.
`retry_chain` ДОЛЖЕН (SHALL) быть детерминированно отсортирован по `attempt_number` (asc) и не содержать дубликатов `workflow_run_id`.

Для historical run без workflow linkage provenance block ДОЛЖЕН (SHALL) оставаться совместимым:
- `workflow_run_id=null`,
- `workflow_status=null`,
- `execution_backend=legacy_pool_runtime`,
- `retry_chain=[]` (или фактическая legacy цепочка, если доступна),
- `legacy_reference` (nullable, при наличии).

#### Scenario: Unified run возвращает структурный retry lineage
- **GIVEN** run имеет initial attempt и минимум один retry
- **WHEN** клиент запрашивает `GET /api/v2/pools/runs/{run_id}`
- **THEN** `provenance.retry_chain` содержит объекты с `attempt_number/attempt_kind/parent_workflow_run_id/status`
- **AND** `provenance.workflow_run_id` указывает на root attempt
- **AND** `provenance.workflow_status` соответствует active attempt

#### Scenario: Retry lineage возвращается в детерминированном порядке
- **GIVEN** run имеет несколько retry попыток
- **WHEN** клиент запрашивает `GET /api/v2/pools/runs/{run_id}`
- **THEN** `provenance.retry_chain` отсортирован по `attempt_number` по возрастанию
- **AND** каждый `workflow_run_id` встречается не более одного раза

### Requirement: OData publication MUST исполняться как workflow step adapter
Система ДОЛЖНА (SHALL) вызывать publication service (OData) как шаг workflow execution graph, а не как отдельный orchestrator runtime.

`POST /api/v2/pools/runs/{run_id}/retry` ДОЛЖЕН (SHALL) запускать retry через workflow runtime для failed subset и НЕ ДОЛЖЕН (SHALL NOT) выполнять direct OData orchestration в API request path.
`POST /api/v2/pools/runs/{run_id}/retry` ДОЛЖЕН (SHALL) возвращать `202 Accepted` и payload принятия retry (`accepted=true`, `workflow_execution_id`, `operation_id` (nullable), `retry_target_summary`), а не синхронный direct publish summary.

#### Scenario: Retry endpoint запускает workflow execution для failed subset
- **GIVEN** pool run имеет `partial_success` и failed targets
- **WHEN** клиент вызывает `POST /api/v2/pools/runs/{run_id}/retry`
- **THEN** создаётся/enqueue workflow execution для failed subset
- **AND** successful targets из прошлых попыток не переисполняются

#### Scenario: Retry endpoint возвращает asynchronous accepted response
- **GIVEN** pool run готов к retry для failed subset
- **WHEN** клиент вызывает `POST /api/v2/pools/runs/{run_id}/retry`
- **THEN** API возвращает `202 Accepted`
- **AND** ответ содержит `workflow_execution_id` или `operation_id` для последующего отслеживания выполнения

#### Scenario: API retry path не вызывает OData напрямую
- **GIVEN** обрабатывается запрос `POST /api/v2/pools/runs/{run_id}/retry`
- **WHEN** система формирует side effects
- **THEN** direct вызов OData клиента из HTTP path не выполняется
- **AND** выполнение происходит через workflow queue/runtime

### Requirement: OData publication rollout MUST быть gated совместимым profile
Система ДОЛЖНА (SHALL) включать unified publication в production только после фиксации compatibility profile для поддерживаемых 1С-конфигураций.

Compatibility profile ДОЛЖЕН (SHALL) храниться как machine-readable source-of-truth в стабильном пути capability:
- `openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.yaml`
- `openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.schema.yaml`

Система ДОЛЖНА (SHALL) валидировать profile по schema в preflight/CI и НЕ ДОЛЖНА (SHALL NOT) зависеть от расположения archived change-папок.
Система ДОЛЖНА (SHALL) проверять `profile_version` как immutable release marker (несовпадение с release profile version = `No-Go`).

#### Scenario: Архивация change не ломает rollout preflight
- **GIVEN** исходный change с profile уже перемещён в `openspec/changes/archive/`
- **WHEN** запускается preflight compatibility
- **THEN** profile успешно читается из стабильного capability path
- **AND** решение `Go/No-Go` формируется без path-dependent ошибок

### Requirement: OData diagnostics MUST иметь фиксированный набор полей
Система ДОЛЖНА (SHALL) сохранять и возвращать по каждой попытке публикации канонический набор:
- `target_database_id`,
- `payload_summary`,
- `http_error` или `transport_error`,
- `domain_error_code`,
- `domain_error_message`,
- `attempt_number`,
- `attempt_timestamp`.

Система МОЖЕТ (MAY) возвращать совместимые alias-поля для обратной совместимости, но канонические поля остаются обязательными для unified API.
Система ДОЛЖНА (SHALL) применять data-minimization для diagnostics payload:
- `payload_summary` не содержит raw документов, credentials и секретов;
- `domain_error_message` и `transport_error` не содержат stack traces и чувствительных инфраструктурных деталей.

#### Scenario: Failed attempt содержит канонические поля diagnostics
- **GIVEN** публикация по target завершается ошибкой
- **WHEN** оператор запрашивает `GET /api/v2/pools/runs/{run_id}`
- **THEN** `publication_attempts[]` содержит `payload_summary`, `domain_error_code`, `domain_error_message`, `attempt_timestamp`
- **AND** присутствует одно из полей `http_error` или `transport_error`

#### Scenario: Diagnostics payload соблюдает redaction policy
- **GIVEN** публикация завершилась инфраструктурной ошибкой
- **WHEN** оператор запрашивает `GET /api/v2/pools/runs/{run_id}`
- **THEN** diagnostics не содержит credentials, raw OData payload и stack trace fragments
- **AND** диагностическая информация остаётся достаточной для triage

### Requirement: Workflows decommission MUST быть запрещён до полной миграции consumers
Система НЕ ДОЛЖНА (SHALL NOT) удалять `workflows` runtime до подтверждённой миграции всех execution consumers на общий контракт исполнения.

Система ДОЛЖНА (SHALL) выполнять decommission preflight на основе machine-readable реестра consumers в стабильном пути capability:
- `openspec/specs/pool-workflow-execution-core/artifacts/execution-consumers-registry.yaml`
- `openspec/specs/pool-workflow-execution-core/artifacts/execution-consumers-registry.schema.yaml`

Система ДОЛЖНА (SHALL) валидировать registry по schema до выполнения decommission preflight и НЕ ДОЛЖНА (SHALL NOT) зависеть от конкретного archived change-id.

#### Scenario: Decommission preflight остаётся валидным после архивирования
- **GIVEN** historical change-артефакты перемещены в архив
- **WHEN** запускается `preflight_workflow_decommission_consumers`
- **THEN** preflight читает registry из стабильного capability path
- **AND** корректно возвращает `Go` или `No-Go` по `migrated` статусам

### Requirement: Tenant confidentiality MUST использовать fail-closed внешний ответ
Система ДОЛЖНА (SHALL) сохранять неразличимость cross-tenant и unknown-run ошибок в pools/runs endpoints.

Payload ошибок ДОЛЖЕН (SHALL):
- не раскрывать `tenant_id` и внутренние инфраструктурные идентификаторы;
- использовать стабильный error envelope для conflict/validation/not-found кейсов;
- оставаться совместимым с существующей клиентской обработкой ошибок.

#### Scenario: Cross-tenant запрос остаётся неразличимым от unknown run
- **GIVEN** клиент обращается к `run_id` из другого tenant
- **WHEN** API формирует ошибку
- **THEN** ответ не отличается по форме/коду от ответа для несуществующего `run_id`
- **AND** в payload отсутствуют tenant-sensitive детали
