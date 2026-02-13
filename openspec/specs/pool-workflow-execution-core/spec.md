# pool-workflow-execution-core Specification

## Purpose
TBD - created by archiving change refactor-unify-pools-workflow-execution-core. Update Purpose after archive.
## Requirements
### Requirement: Pool runs MUST исполняться через workflow execution runtime
Система ДОЛЖНА (SHALL) выполнять `Pool Run` через единый workflow runtime, который отвечает за lifecycle, enqueue, retry, audit и step orchestration.

`pools` НЕ ДОЛЖЕН (SHALL NOT) иметь отдельный независимый runtime lifecycle для исполнения run-ов.

#### Scenario: Запуск unsafe pool run создаёт и запускает workflow run
- **GIVEN** пользователь инициирует запуск `/api/v2/pools/runs`
- **AND** run запрошен в режиме `unsafe`
- **WHEN** система принимает валидный запрос
- **THEN** создаётся workflow run как фактическая единица исполнения
- **AND** pool run хранит reference на соответствующий workflow run
- **AND** публикационные шаги enqueue без ручного подтверждения

#### Scenario: Запуск safe pool run создаёт workflow run без старта публикации
- **GIVEN** пользователь инициирует запуск `/api/v2/pools/runs`
- **AND** run запрошен в режиме `safe`
- **WHEN** система принимает валидный запрос
- **THEN** создаётся workflow run с `approval_required=true` и `approval_state=preparing`
- **AND** выполняются pre-publish шаги до ручного решения оператора
- **AND** после завершения pre-publish run переходит в `approval_state=awaiting_approval`
- **AND** публикационные шаги НЕ запускаются до явной команды подтверждения

### Requirement: Safe mode MUST иметь явный approval gate
Система ДОЛЖНА (SHALL) поддерживать явные команды фасада для безопасного режима:
- `confirm-publication` — разрешает переход к публикационным шагам;
- `abort-publication` — завершает исполнение без публикации.

Система ДОЛЖНА (SHALL) завершать pre-publish этап (`prepare_input`, `distribution_calculation`, `reconciliation_report`) до ожидания ручного решения в `safe` режиме.

Система ДОЛЖНА (SHALL) фиксировать фазу safe-flow через `approval_state`:
- `preparing` — pre-publish этап ещё выполняется;
- `awaiting_approval` — pre-publish завершён, run ожидает ручное решение;
- `approved` — подтверждение публикации получено;
- `not_required` — для `unsafe` режима.

#### Scenario: Подтверждение публикации переводит safe run в очередь исполнения
- **GIVEN** pool run находится в `safe` режиме и ожидает подтверждения
- **WHEN** оператор отправляет команду `confirm-publication`
- **THEN** publication step enqueue в workflow runtime
- **AND** run переходит из `validated` (`awaiting_approval`) в `validated` (`queued`) или `publishing` по факту выполнения

#### Scenario: Отмена публикации завершает safe run как failed
- **GIVEN** pool run находится в `safe` режиме и ожидает подтверждения
- **WHEN** оператор отправляет команду `abort-publication`
- **THEN** связанный workflow run помечается `cancelled`
- **AND** facade проецирует итоговый pool status как `failed`

#### Scenario: Safe run предоставляет pre-publish диагностику до подтверждения
- **GIVEN** run запущен в `safe` режиме
- **WHEN** pre-publish этап завершён
- **THEN** оператор получает diagnostics/артефакты проверки до публикации
- **AND** `publication_odata` не enqueue до `confirm-publication`

#### Scenario: Во время pre-publish safe run проецируется как validated preparing
- **GIVEN** run запущен в `safe` режиме
- **AND** pre-publish шаги ещё выполняются
- **WHEN** клиент запрашивает детали run
- **THEN** фасад возвращает статус `validated`
- **AND** поле `status_reason` равно `preparing`

### Requirement: Safe commands MUST быть выражены явными идемпотентными API-операциями
Система ДОЛЖНА (SHALL) поддерживать команды безопасного режима как отдельные endpoint'ы:
- `POST /api/v2/pools/runs/{run_id}/confirm-publication`;
- `POST /api/v2/pools/runs/{run_id}/abort-publication`.

Система ДОЛЖНА (SHALL) требовать `Idempotency-Key` header для `confirm-publication` и `abort-publication`.

Система ДОЛЖНА (SHALL) дедуплицировать команды по ключу `(run_id, command_type, idempotency_key)` и возвращать deterministic replay без side effects.

Система ДОЛЖНА (SHALL) применять эти команды только к safe-run (`approval_required=true`); для `unsafe` команда ДОЛЖНА (SHALL) возвращать business conflict.

Система ДОЛЖНА (SHALL) трактовать идемпотентность команд как отсутствие побочных эффектов (включая duplicate enqueue) при повторном вызове; response class (`202`/`200`/`409`) определяется детерминированной state-matrix.

#### Scenario: Повторный confirm не создаёт дублирующий enqueue
- **GIVEN** `confirm-publication` уже успешно выполнен для `safe` run
- **WHEN** оператор повторно вызывает `confirm-publication`
- **THEN** состояние run не расходится с предыдущим результатом
- **AND** дополнительная публикационная задача не ставится в очередь повторно

#### Scenario: Повтор команды с тем же Idempotency-Key возвращает replay без побочных эффектов
- **GIVEN** `confirm-publication` уже принят с конкретным `Idempotency-Key`
- **WHEN** клиент повторяет тот же запрос с тем же `Idempotency-Key`
- **THEN** система возвращает deterministic replay исходного outcome (`202` или `200`)
- **AND** состояние run и очередь задач не меняются

#### Scenario: Отсутствие Idempotency-Key отклоняется как некорректный запрос
- **GIVEN** оператор вызывает `confirm-publication` или `abort-publication`
- **AND** header `Idempotency-Key` отсутствует
- **WHEN** система валидирует команду
- **THEN** возвращается `400 Bad Request`
- **AND** состояние run не изменяется

#### Scenario: Команда на terminal run отклоняется бизнес-ошибкой
- **GIVEN** run находится в terminal status (`published`, `partial_success` или `failed`)
- **AND** `terminal_reason` не равен `aborted_by_operator`
- **WHEN** оператор вызывает `confirm-publication` или `abort-publication`
- **THEN** система возвращает business conflict
- **AND** состояние run не изменяется

#### Scenario: Повторный abort после operator-abort возвращает idempotent no-op
- **GIVEN** run уже завершён через `abort-publication`
- **AND** `terminal_reason=aborted_by_operator`
- **WHEN** оператор повторно вызывает `abort-publication`
- **THEN** система возвращает idempotent no-op
- **AND** состояние run не изменяется

#### Scenario: Abort после старта publication_odata отклоняется бизнес-ошибкой
- **GIVEN** `publication_odata` уже начал исполнение
- **WHEN** оператор вызывает `abort-publication`
- **THEN** система возвращает business conflict
- **AND** состояние run не изменяется

### Requirement: Safe commands MUST иметь полную state-matrix без неявных интерпретаций
Система ДОЛЖНА (SHALL) применять следующую state-matrix команд:
- общая precondition: header `Idempotency-Key` обязателен; при отсутствии -> `400 Bad Request`;
- `confirm-publication`:
  - `approval_state=awaiting_approval` и facade `validated/awaiting_approval` -> `202 Accepted` и enqueue публикации;
  - `approval_state=approved` и facade `validated/queued` или `publishing` -> `200 OK` idempotent no-op;
  - `approval_state in {preparing,not_required}` -> `409` business conflict;
  - terminal state -> `409` business conflict.
- `abort-publication`:
  - `approval_required=true` + facade `validated/preparing`, `validated/awaiting_approval` или `validated/queued` и `publication_odata` не начат -> `202 Accepted` и отмена run;
  - `approval_state=not_required` (`unsafe`) -> `409` business conflict;
  - `publication_odata` уже начат -> `409` business conflict;
  - terminal + `terminal_reason=aborted_by_operator` -> `200 OK` idempotent no-op;
  - остальные terminal state -> `409` business conflict.

#### Scenario: Confirm в preparing отклоняется до завершения pre-publish
- **GIVEN** run находится в `approval_state=preparing`
- **WHEN** оператор вызывает `confirm-publication`
- **THEN** система возвращает business conflict
- **AND** состояние run не изменяется

#### Scenario: Confirm в validated queued возвращает idempotent no-op
- **GIVEN** публикация уже подтверждена
- **AND** `approval_state=approved`
- **AND** facade возвращает `validated` с `status_reason=queued`
- **WHEN** оператор повторно вызывает `confirm-publication`
- **THEN** система возвращает idempotent no-op
- **AND** дополнительный enqueue не создаётся

#### Scenario: Confirm из awaiting_approval возвращает 202 Accepted
- **GIVEN** run находится в `approval_state=awaiting_approval`
- **WHEN** оператор вызывает `confirm-publication`
- **THEN** система возвращает `202 Accepted`
- **AND** publication step ставится в очередь единожды

#### Scenario: Abort для unsafe run отклоняется как неразрешённая команда
- **GIVEN** run запущен в `unsafe` режиме
- **AND** `approval_state=not_required`
- **WHEN** оператор вызывает `abort-publication`
- **THEN** система возвращает business conflict
- **AND** состояние run не изменяется

### Requirement: Safe command conflicts MUST возвращать канонический error payload
Система ДОЛЖНА (SHALL) возвращать для `409 Conflict` на `confirm-publication` / `abort-publication` единый payload:
- `error_code` (stable machine code),
- `error_message` (human-readable text),
- `conflict_reason` (enum: `not_safe_run`, `awaiting_pre_publish`, `publication_started`, `terminal_state`, `idempotency_key_reused`),
- `retryable` (boolean),
- `run_id`.

#### Scenario: Конфликт команды возвращает каноническую структуру ошибки
- **GIVEN** команда `confirm-publication` вызвана в `approval_state=preparing`
- **WHEN** система отклоняет команду
- **THEN** HTTP ответ равен `409 Conflict`
- **AND** тело ответа содержит `error_code`, `error_message`, `conflict_reason`, `retryable`, `run_id`

#### Scenario: Reuse Idempotency-Key с несовместимой командой возвращает idempotency_key_reused
- **GIVEN** ключ `Idempotency-Key` уже использован для другой семантики команды того же run
- **WHEN** клиент повторно отправляет команду с тем же ключом
- **THEN** система возвращает `409 Conflict`
- **AND** `conflict_reason` равно `idempotency_key_reused`

### Requirement: Safe commands MUST использовать Variant A pipeline (transactional command log + transactional outbox)
Система ДОЛЖНА (SHALL) обрабатывать `confirm-publication` и `abort-publication` через транзакционный Variant A pipeline:
- `pool_run_command_log` как канонический storage outcome safe-команды (`run_id`, `command_type`, `idempotency_key`, command result class, response snapshot, CAS outcome, timestamps);
- `pool_run_command_outbox` как канонический storage side-effect intents (enqueue publication/cancel execution), публикуемых только после commit;
- single-winner CAS для конкурентных safe-команд на одном run (`approval_state`, `publication_step_state`, `terminal_reason`) с детерминированным outcome проигравшей команды.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять direct enqueue/cancel side effects из HTTP request path до фиксации транзакции command log/outbox.

Система ДОЛЖНА (SHALL) обеспечивать deterministic replay по `(run_id, command_type, idempotency_key)` через сохранённый response snapshot без повторных side effects.

#### Scenario: Успешный confirm фиксирует command outcome и outbox атомарно
- **GIVEN** `approval_state=awaiting_approval`
- **WHEN** оператор вызывает `confirm-publication` с новым `Idempotency-Key`
- **THEN** система в одной транзакции выполняет CAS-переход, сохраняет запись в `pool_run_command_log` и создаёт запись в `pool_run_command_outbox`
- **AND** ответ `202 Accepted` возвращается только после commit

#### Scenario: Outbox side effect публикуется только после commit
- **GIVEN** создана pending запись `pool_run_command_outbox`
- **WHEN** outbox-dispatcher обрабатывает очередь
- **THEN** side effect (`enqueue publication` или `cancel execution`) публикуется в `commands:worker:workflows` только для committed записи
- **AND** при сбое dispatcher допускается idempotent повтор без duplicate business effect

#### Scenario: Гонка confirm и abort разрешается single-winner CAS
- **GIVEN** два оператора почти одновременно вызывают `confirm-publication` и `abort-publication` для одного run
- **WHEN** система применяет Variant A CAS-правило
- **THEN** только одна команда выигрывает переход состояния и получает side effect intent в outbox
- **AND** проигравшая команда получает детерминированный conflict/no-op outcome без изменения состояния

#### Scenario: Replay по тому же ключу возвращает сохранённый snapshot
- **GIVEN** safe-команда уже зафиксирована в `pool_run_command_log`
- **WHEN** клиент повторяет тот же запрос с тем же `Idempotency-Key`
- **THEN** система возвращает сохранённый response snapshot
- **AND** не создаёт новую outbox-запись и не выполняет duplicate side effect

### Requirement: Pool status projection MUST быть канонической и детерминированной
Система ДОЛЖНА (SHALL) использовать единый mapping статусов между workflow runtime и pools facade:
- `pool:draft` — только до создания workflow run;
- `approval_required=true + approved_at is null + approval_state=preparing -> pool:validated` с `status_reason=preparing` (workflow status может быть `pending` или `running`);
- `approval_required=true + approved_at is null + approval_state=awaiting_approval -> pool:validated` с `status_reason=awaiting_approval`;
- `publication_odata` не started + (`approval_required=false OR approved_at is not null`) + `workflow.status in {pending, running} -> pool:validated` с `status_reason=queued`;
- `publication_odata` started + (`approval_required=false` OR `approved_at is not null`) -> pool:publishing;
- `workflow:completed + failed_targets=0 -> pool:published`;
- `workflow:completed + failed_targets>0 -> pool:partial_success`;
- `workflow:failed|cancelled -> pool:failed`.

Система ДОЛЖНА (SHALL) использовать `status_reason` только для `pool:validated` с допустимыми значениями `preparing|awaiting_approval|queued`; для остальных pool-статусов `status_reason` ДОЛЖЕН (SHALL) быть `null`.

Система ДОЛЖНА (SHALL) считать `approval_state`, `approved_at`, `publication_odata started/not started` primary сигналами проекции; `workflow.status` ДОЛЖЕН (SHALL) быть secondary сигналом.

#### Scenario: Завершение workflow с failed targets даёт partial_success
- **GIVEN** workflow run завершён со статусом `completed`
- **AND** publication summary содержит failed targets
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `partial_success`
- **AND** в ответе остаётся ссылка на исходный workflow run

#### Scenario: Pending workflow с approval_required проецируется как validated awaiting_approval
- **GIVEN** workflow run создан со статусом `pending`
- **AND** `approval_required=true`
- **AND** `approval_state=awaiting_approval`
- **AND** подтверждение публикации ещё не получено
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `validated`
- **AND** поле `status_reason` равно `awaiting_approval`

#### Scenario: Safe pre-publish в running проецируется как validated preparing
- **GIVEN** workflow run находится в состоянии `running`
- **AND** `approval_required=true`
- **AND** `approved_at is null`
- **AND** `approval_state=preparing`
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `validated`
- **AND** поле `status_reason` равно `preparing`

#### Scenario: Для non-validated статусов status_reason отсутствует
- **GIVEN** шаг `publication_odata` уже started
- **AND** (`approval_required=false` ИЛИ `approved_at is not null`)
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `publishing`
- **AND** `status_reason` равен `null`

### Requirement: Safe-flow state machine MUST исключать архитектурно неоднозначные проекции
Система ДОЛЖНА (SHALL) обеспечивать инварианты safe/unsafe state machine:
- при `approval_required=true` и `approved_at is null` фасад НЕ ДОЛЖЕН (SHALL NOT) проецировать статус `publishing`;
- `publishing` допустим только когда `approval_required=false` ИЛИ `approved_at is not null`;
- `abort-publication` после старта шага `publication_odata` ДОЛЖЕН (SHALL) возвращать business conflict без изменения состояния.

#### Scenario: Safe run без подтверждения не может быть publishing
- **GIVEN** run находится в `safe` режиме
- **AND** `approval_required=true`
- **AND** `approved_at is null`
- **WHEN** клиент запрашивает детали run
- **THEN** фасад НЕ возвращает статус `publishing`
- **AND** run остаётся в `validated` с `status_reason=preparing` или `status_reason=awaiting_approval`

#### Scenario: Unsafe running run проецируется как publishing без approval ожидания
- **GIVEN** run запущен в `unsafe` режиме
- **AND** workflow run находится в состоянии `running`
- **WHEN** клиент запрашивает детали run
- **THEN** фасад возвращает статус `publishing`
- **AND** `status_reason` равен `null`

### Requirement: Approval state MUST быть каноническим runtime-полем и возвращаться в API
Система ДОЛЖНА (SHALL) хранить `approval_state` как source-of-truth в metadata workflow execution и использовать его в status projection.

Система ДОЛЖНА (SHALL) использовать ограниченный enum `approval_state`:
- `not_required`,
- `preparing`,
- `awaiting_approval`,
- `approved`.

Система ДОЛЖНА (SHALL) возвращать `approval_state` в `GET /api/v2/pools/runs/{run_id}` для unified execution.

Для historical/legacy run поле `approval_state` МОЖЕТ (MAY) быть `null`.

#### Scenario: Unified run details содержит approval_state
- **GIVEN** run исполняется через `workflow_core`
- **WHEN** клиент запрашивает `GET /api/v2/pools/runs/{run_id}`
- **THEN** ответ содержит поле `approval_state`
- **AND** значение согласовано с runtime metadata workflow execution

### Requirement: Tenant boundary MUST сохраняться между pool и workflow run
Система ДОЛЖНА (SHALL) обеспечивать tenant-изоляцию при запуске, чтении и retry:
- `pool_run.tenant_id` и `workflow_execution.tenant_id` обязаны совпадать;
- доступ к связанному workflow run из другого tenant-контекста НЕ ДОЛЖЕН (SHALL NOT) быть возможен.

#### Scenario: Cross-tenant доступ к workflow provenance отклоняется
- **GIVEN** pool run создан в tenant `A`
- **WHEN** пользователь tenant `B` запрашивает детали этого run
- **THEN** система отклоняет запрос как недоступный в текущем tenant context
- **AND** данные workflow provenance не раскрываются

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

### Requirement: Workflow tenant model MUST быть совместим с multi-consumer runtime
Система ДОЛЖНА (SHALL) расширить `WorkflowExecution` полями `tenant_id` и `execution_consumer`.

Для `execution_consumer=pools` поле `tenant_id` ДОЛЖНО (SHALL) быть обязательным.

Для historical/non-tenant consumers поле `tenant_id` МОЖЕТ (MAY) быть `null` до завершения их миграции.

#### Scenario: Non-pools consumer может существовать без tenant_id на переходном этапе
- **GIVEN** workflow run принадлежит consumer, отличному от `pools`
- **WHEN** запись создана до tenant-миграции этого consumer
- **THEN** `tenant_id` может быть `null` без нарушения контракта pools
- **AND** pools tenant-check не ослабляется

### Requirement: Import templates и execution plan MUST быть разделены терминологически и технически
Система ДОЛЖНА (SHALL) использовать разделённые сущности:
- `PoolImportSchemaTemplate` как execution-core термин для доменного шаблона импорта (`PoolSchemaTemplate` из foundation change);
- `PoolExecutionPlan` как runtime artifact, полученный компилятором для workflow graph.

Система ДОЛЖНА (SHALL) иметь детерминированный compiler `PoolImportSchemaTemplate + run_context -> PoolExecutionPlan`.

Система ДОЛЖНА (SHALL) трактовать foundation-поле `workflow_binding` на import template как optional compiler hint и НЕ ДОЛЖНА (SHALL NOT) трактовать его как отдельный runtime execution-template.

#### Scenario: Одинаковый pool template компилируется детерминированно
- **GIVEN** одинаковые версия import template, входные параметры, период и `source_hash`
- **WHEN** выполняется компиляция execution plan
- **THEN** структура workflow graph и binding mapping совпадают
- **AND** runtime provenance может быть воспроизведён для диагностики

#### Scenario: Legacy template с workflow_binding остаётся совместимым
- **GIVEN** import template был создан в foundation-change и содержит `workflow_binding`
- **WHEN** запускается unified execution
- **THEN** template принимается без изменения публичного API
- **AND** `workflow_binding` используется только как hint для compiler

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

### Requirement: OData external document identity MUST использовать strategy-based resolver
Система ДОЛЖНА (SHALL) поддерживать strategy-based resolver идентификатора внешнего документа:
- primary strategy: стабильный GUID (`_IDRRef` или `Ref_Key`);
- fallback strategy: детерминированный `ExternalRunKey` (`runkey-<sha256[:32]>` от `run_id + target_database_id + document_kind + period`).

Система ДОЛЖНА (SHALL) сохранять выбранную стратегию и итоговый идентификатор в audit/provenance.

#### Scenario: GUID недоступен, применяется fallback стратегия
- **GIVEN** целевая конфигурация не возвращает стабильный GUID
- **WHEN** выполняется публикация
- **THEN** система использует `ExternalRunKey`
- **AND** фиксирует fallback-стратегию в audit/provenance

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

### Requirement: Publication retry contract MUST быть единым для pools и workflow runtime
Система ДОЛЖНА (SHALL) поддерживать доменный контракт `max_attempts_total=5` (включая initial attempt) для публикации в OData.

Контракт ДОЛЖЕН (SHALL) быть семантически эквивалентен foundation-формулировке `max_attempts=5`.

Система ДОЛЖНА (SHALL) поддерживать `retry_interval_seconds` как конфигурируемый параметр, при этом эффективный интервал НЕ ДОЛЖЕН (SHALL NOT) превышать 120 секунд.

Система ДОЛЖНА (SHALL) исполнять retry endpoint `POST /api/v2/pools/runs/{run_id}/retry` только для failed subset, не дублируя успешные цели.

#### Scenario: Retry повторно исполняет только failed subset
- **GIVEN** pool run имеет `partial_success` и набор failed targets
- **WHEN** клиент вызывает retry endpoint
- **THEN** система создаёт/запускает workflow execution только для failed subset
- **AND** успешные публикации из предыдущих попыток не повторяются

#### Scenario: Конфигурация retry интервала выше лимита ограничивается
- **GIVEN** для run задан `retry_interval_seconds` выше 120 секунд
- **WHEN** runtime формирует retry policy
- **THEN** эффективный интервал устанавливается не выше 120 секунд
- **AND** это значение отражается в runtime metadata

### Requirement: Queueing contract MUST быть фиксирован для phase 1
Система ДОЛЖНА (SHALL) отправлять workflow execution для pools в существующий workflow stream `commands:worker:workflows` с приоритетом `normal` по умолчанию.

Система НЕ ДОЛЖНА (SHALL NOT) вводить отдельный SLA/priority lane для pools в рамках этого change.

#### Scenario: Pool run enqueue использует workflow stream phase 1
- **WHEN** запускается pool run через unified execution core
- **THEN** enqueue выполняется в workflow stream `commands:worker:workflows`
- **AND** execution config использует приоритет `normal`, если явно не задано иначе в будущем extension

#### Scenario: Safe run enqueue publication шага выполняется только после confirm-publication
- **GIVEN** run запущен в `safe` режиме
- **AND** подтверждение ещё не выполнено
- **WHEN** оператор запрашивает состояние очереди
- **THEN** publication step отсутствует в worker queue
- **AND** pre-publish шаги могут быть уже выполнены или находиться в обработке
- **AND** после `confirm-publication` publication step enqueue в `commands:worker:workflows`

### Requirement: Migration MUST сохранять historical runs и идемпотентность
Система ДОЛЖНА (SHALL) обеспечить миграцию/совместимость, при которой historical pool runs остаются читаемыми, а доменный idempotency key продолжает предотвращать дубли исполнения.

Система ДОЛЖНА (SHALL) выполнять cutover через dual-write и dual-read до достижения критериев стабилизации.

Система ДОЛЖНА (SHALL) иметь rollback criteria и rollback-path, позволяющий вернуть execution routing на legacy path без отката миграций схемы.

#### Scenario: Historical run читается после включения unified execution
- **GIVEN** run был создан до перевода исполнения на workflow runtime
- **WHEN** оператор открывает run details после релиза
- **THEN** система возвращает совместимое представление run
- **AND** audit/provenance остаются доступными

#### Scenario: Идемпотентный ключ сохраняет поведение после перевода на workflow runtime
- **GIVEN** существует run с ключом `pool_id + period + direction + source_hash`
- **WHEN** пользователь повторно инициирует запуск с тем же ключом
- **THEN** система выполняет upsert существующего набора результатов
- **AND** дубликаты документов/публикаций не создаются

#### Scenario: Rollback возвращает routing без потери связей
- **GIVEN** после cutover обнаружена блокирующая деградация по SLO или tenant boundary
- **WHEN** команда запускает rollback-path
- **THEN** create/start routing возвращается на legacy execution path
- **AND** linkage `pool_run <-> workflow_run` и данные dual-write сохраняются для последующего расследования

### Requirement: Runtime source-of-truth MUST быть единым между change-ами
Система ДОЛЖНА (SHALL) трактовать runtime-семантику `pool-distribution-runs` и `pool-odata-publication` через требования этого capability.

Foundation change `add-intercompany-pool-distribution-module` ДОЛЖЕН (SHALL) использоваться как источник domain vocabulary, но НЕ ДОЛЖЕН (SHALL NOT) переопределять execution-правила после принятия этого change.

#### Scenario: Конфликт интерпретаций runtime разрешается в пользу execution-core spec
- **GIVEN** в foundation change и execution-core change есть различающиеся формулировки runtime-поведения
- **WHEN** команда реализует исполнение `pools/runs*`
- **THEN** runtime реализуется по требованиям `pool-workflow-execution-core`
- **AND** foundation change используется только для доменных терминов и baseline API surface

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

