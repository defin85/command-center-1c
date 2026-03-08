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
- `workflow:completed + (approval_required=true AND approved_at is null) -> pool:validated` с `status_reason=awaiting_approval`;
- `workflow:completed + (approval_required=false OR approved_at is not null) + publication_step_state=completed + failed_targets=0 -> pool:published`;
- `workflow:completed + (approval_required=false OR approved_at is not null) + publication_step_state=completed + failed_targets>0 -> pool:partial_success`;
- `workflow:completed + execution_backend=workflow_core + publication_step_state is null + projection_timestamp < publication_hardening_cutoff + failed_targets=0 -> pool:published`;
- `workflow:completed + execution_backend=workflow_core + publication_step_state is null + projection_timestamp < publication_hardening_cutoff + failed_targets>0 -> pool:partial_success`;
- `workflow:completed + execution_backend=legacy_pool_runtime + publication_step_state is null + failed_targets=0 -> pool:published`;
- `workflow:completed + execution_backend=legacy_pool_runtime + publication_step_state is null + failed_targets>0 -> pool:partial_success`;
- `workflow:completed + (approval_required=false OR approved_at is not null) + publication_step_state!=completed -> pool:failed`;
- `workflow:failed|cancelled -> pool:failed`.

Система ДОЛЖНА (SHALL) использовать `status_reason` только для `pool:validated` с допустимыми значениями `preparing|awaiting_approval|queued`; для остальных pool-статусов `status_reason` ДОЛЖЕН (SHALL) быть `null`.

Система ДОЛЖНА (SHALL) считать `approval_state`, `approved_at`, `publication_odata started/not started` и `publication_step_state` primary сигналами проекции; `workflow.status` ДОЛЖЕН (SHALL) быть secondary сигналом.

#### Scenario: Завершение workflow с failed targets даёт partial_success
- **GIVEN** workflow run завершён со статусом `completed`
- **AND** publication summary содержит failed targets
- **AND** `publication_step_state=completed`
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

#### Scenario: Completed workflow без завершённого publication-step не может быть published
- **GIVEN** workflow run имеет `status=completed`
- **AND** (`approval_required=false` ИЛИ `approved_at is not null`)
- **AND** `publication_step_state!=completed`
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `failed`
- **AND** фасад НЕ ДОЛЖЕН (SHALL NOT) возвращать статус `published`

#### Scenario: Historical legacy run сохраняет прежнюю terminal-проекцию при неизвестном publication_step_state
- **GIVEN** workflow run имеет `status=completed`
- **AND** `execution_backend=legacy_pool_runtime`
- **AND** `publication_step_state` отсутствует (`null`/пусто)
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад использует legacy fallback по `failed_targets`
- **AND** historical run остаётся читаемым без forced-перехода в `failed`

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
- `PoolWorkflowDefinition` как переиспользуемый blueprint процесса;
- `PoolExecutionPlanSnapshot` как immutable runtime snapshot конкретного запуска.

Система ДОЛЖНА (SHALL) иметь детерминированный compiler, который разделяет:
- compile-time результат: `PoolImportSchemaTemplate + structural_context -> PoolWorkflowDefinition`;
- run-time результат: `PoolRun + request_context -> PoolExecutionPlanSnapshot`.

`definition_key` ДОЛЖЕН (SHALL) строиться только из структурных признаков (`pool_id`, `direction`, `mode`, template version/schema content, DAG structure, workflow binding hint) и НЕ ДОЛЖЕН (SHALL NOT) зависеть от `period_start`, `period_end`, `run_input`, idempotency key.

Система ДОЛЖНА (SHALL) трактовать foundation-поле `workflow_binding` на import template как optional compiler hint и НЕ ДОЛЖНА (SHALL NOT) трактовать его как отдельный runtime execution-template.

#### Scenario: Разные period/run_input переиспользуют один workflow definition
- **GIVEN** два запуска одного `pool_id` с одинаковыми `direction/mode` и одинаковой версией import template
- **AND** `period_*` и `run_input` различаются
- **WHEN** backend компилирует workflow для обоих запусков
- **THEN** `definition_key` и ссылка на workflow definition совпадают
- **AND** каждый запуск получает собственный `PoolExecutionPlanSnapshot` с его `period_*` и `run_input`

#### Scenario: Структурное изменение создаёт новый workflow definition
- **GIVEN** для того же `pool_id` изменилась версия schema template или compiled DAG structure
- **WHEN** backend компилирует workflow definition
- **THEN** вычисляется новый `definition_key`
- **AND** создаётся новая версия workflow definition

#### Scenario: Legacy template с workflow_binding остаётся совместимым
- **GIVEN** import template содержит `workflow_binding`
- **WHEN** запускается unified execution
- **THEN** template принимается без изменения публичного API
- **AND** `workflow_binding` используется только как compiler hint

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
Система ДОЛЖНА (SHALL) выполнить миграцию так, чтобы historical pool runs оставались читаемыми, а create-run idempotency использовал canonicalized `run_input` fingerprint вместо legacy `source_hash`.

Система ДОЛЖНА (SHALL) иметь rollback criteria и rollback-path для возврата execution routing без потери связей run/provenance.

Система ДОЛЖНА (SHALL) сопровождать breaking удаление `source_hash` обновлением OpenAPI-примеров и release notes для интеграторов.

#### Scenario: Идемпотентный ключ после миграции вычисляется из canonicalized run_input
- **GIVEN** клиент отправляет create-run с `run_input`
- **WHEN** backend вычисляет idempotency fingerprint
- **THEN** fingerprint зависит от canonicalized `run_input` и контекста запуска (`pool_id`, `period`, `direction`)
- **AND** поле `source_hash` не участвует в вычислении

#### Scenario: Breaking cutover документирован для интеграторов
- **GIVEN** система переходит на контракт без `source_hash`
- **WHEN** публикуется новая версия OpenAPI
- **THEN** release notes содержат migration guidance и обновлённые примеры create-run payload
- **AND** интеграторы могут перейти на `run_input` без двусмысленности контракта

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

### Requirement: Pool run create contract MUST использовать структурированный run_input как source-of-truth
Система ДОЛЖНА (SHALL) расширить контракт создания run структурированным полем `run_input` и валидировать его по направлению исполнения.

Система ДОЛЖНА (SHALL) сохранять `run_input` в состоянии run и передавать его в workflow `input_context` для шагов подготовки и расчёта распределения.

#### Scenario: Top-down run_input передаётся в workflow execution context
- **GIVEN** run создаётся с направлением `top_down` и стартовой суммой в `run_input`
- **WHEN** создаётся связанный workflow run
- **THEN** `run_input` доступен в `input_context` workflow
- **AND** шаги `prepare_input` и `distribution_calculation` используют его как входные данные

#### Scenario: Неполный run_input отклоняется на create-run
- **GIVEN** клиент отправляет `direction=top_down` без обязательных полей `run_input`
- **WHEN** backend валидирует запрос создания run
- **THEN** возвращается `400` с ошибкой валидации
- **AND** run не создаётся

### Requirement: Pool run idempotency fingerprint MUST учитывать canonicalized run_input
Система ДОЛЖНА (SHALL) включать canonicalized `run_input` в вычисление idempotency fingerprint для create/upsert run.

Система НЕ ДОЛЖНА (SHALL NOT) переиспользовать один и тот же run, если direction-specific входные данные различаются.

Канонизация `run_input` ДОЛЖНА (SHALL) быть детерминированной: semantically-equivalent payload должен давать одинаковый fingerprint независимо от порядка ключей и форматирования JSON.

Профиль canonicalization ДОЛЖЕН (SHALL) включать:
- лексикографическую сортировку ключей объектов;
- сохранение порядка элементов массивов;
- нормализацию денежных значений в fixed-scale decimal string;
- сериализацию без зависимости от whitespace/formatting входного JSON.

#### Scenario: Изменение стартовой суммы создаёт новый idempotency fingerprint
- **GIVEN** два запроса create-run с одинаковыми `pool_id`, `period`, `direction`
- **AND** стартовая сумма в `run_input` различается
- **WHEN** backend вычисляет idempotency fingerprint
- **THEN** fingerprint различается
- **AND** второй запрос не переиспользует run первого запуска

#### Scenario: Повтор того же run_input переиспользует существующий run
- **GIVEN** create-run уже выполнен для конкретного canonicalized `run_input`
- **WHEN** клиент повторяет create-run с теми же полями
- **THEN** система возвращает существующий run по idempotency
- **AND** дубликат run не создаётся

#### Scenario: Семантически эквивалентный JSON даёт тот же fingerprint
- **GIVEN** два create-run payload с одинаковым смыслом `run_input`, но разным порядком ключей
- **WHEN** backend canonicalizes `run_input`
- **THEN** вычисленный idempotency fingerprint совпадает
- **AND** система не создаёт дублирующий run

### Requirement: Create-run API MUST удалить source_hash из публичного контракта
Система ДОЛЖНА (SHALL) удалить поле `source_hash` из публичного контракта `POST /api/v2/pools/runs/` и из формулы idempotency key.

Система ДОЛЖНА (SHALL) сохранять читаемость historical run после удаления `source_hash` из create-path.

Публичный read-контракт run ДОЛЖЕН (SHALL) возвращать:
- `run_input` как nullable поле;
- `input_contract_version` (`run_input_v1` или `legacy_pre_run_input`);
- без публичного поля `source_hash`.

#### Scenario: Запрос create-run с source_hash отклоняется как невалидный контракт
- **GIVEN** клиент отправляет create-run с полем `source_hash`
- **WHEN** backend валидирует payload по обновлённому контракту
- **THEN** возвращается `400` с ошибкой валидации неизвестного/запрещённого поля
- **AND** run не создаётся

#### Scenario: Historical run остаётся читаемым после удаления source_hash из create-path
- **GIVEN** в системе есть historical run, созданный до обновления контракта
- **WHEN** клиент запрашивает список или детали run
- **THEN** API возвращает run без ошибки десериализации с `run_input=null`
- **AND** поле `input_contract_version` равно `legacy_pre_run_input`
- **AND** данные run доступны для UI мониторинга и safe-flow операций

### Requirement: Create-run validation errors MUST использовать Problem Details контракт
Система ДОЛЖНА (SHALL) возвращать ошибки валидации create-run в формате `application/problem+json`.

Problem payload ДОЛЖЕН (SHALL) содержать `type`, `title`, `status`, `detail`, `code`.

#### Scenario: source_hash в create-run возвращает Problem Details ошибку
- **GIVEN** клиент отправляет create-run с запрещённым полем `source_hash`
- **WHEN** backend формирует ответ об ошибке
- **THEN** response content-type равен `application/problem+json`
- **AND** payload содержит `status=400` и machine-readable `code`

### Requirement: Pool workflow compiler MUST формировать pinned binding на system-managed runtime templates
Система ДОЛЖНА (SHALL) компилировать operation nodes pool workflow с `operation_ref(binding_mode="pinned_exposure")`, где указываются `template_exposure_id` и `template_exposure_revision` из system-managed pool runtime registry.

Pool workflow node НЕ ДОЛЖЕН (SHALL NOT) исполняться в режиме `alias_latest` в production path.

#### Scenario: Компиляция pool run фиксирует pinned exposure provenance
- **GIVEN** system-managed registry содержит активный alias `pool.prepare_input`
- **WHEN** компилятор строит workflow DAG для pool run
- **THEN** node `prepare_input` содержит `operation_ref.binding_mode="pinned_exposure"`
- **AND** в node заполнены `template_exposure_id` и `template_exposure_revision`

#### Scenario: Missing binding в registry блокирует создание run fail-closed
- **GIVEN** в system-managed registry отсутствует alias `pool.distribution_calculation.top_down`
- **WHEN** система пытается создать workflow execution plan для top_down run
- **THEN** создание run отклоняется fail-closed бизнес-ошибкой
- **AND** код ошибки равен `POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED`
- **AND** enqueue шагов не выполняется

### Requirement: Pool runtime steps MUST исполняться через PoolDomainBackend
Система ДОЛЖНА (SHALL) выполнять pool runtime operation nodes через выделенный domain execution path, а не через generic CLI/OData backends (`ibcmd_cli`, `designer_cli`, `create|update|delete|query`).

Для execution lane `workflow_core` система ДОЛЖНА (SHALL) использовать выделенный `poolops`-драйвер/адаптер, который исполняет `pool.*` шаги через pool domain runtime контракт.

Система НЕ ДОЛЖНА (SHALL NOT) завершать `pool.*` operation node статусом `completed` при отсутствии executor/adapter.

#### Scenario: distribution_calculation в workflow_core исполняется через poolops path без generic fallback
- **GIVEN** workflow run дошёл до шага `distribution_calculation`
- **AND** исполнение происходит в lane `commands:worker:workflows`
- **WHEN** runtime выбирает backend для operation node `pool.distribution_calculation.top_down`
- **THEN** выбран выделенный `poolops` execution path
- **AND** generic драйверы (`odata`, `ibcmd`, `cli`, `ras`) не вызываются

#### Scenario: Missing pool executor завершает workflow fail-closed
- **GIVEN** worker обрабатывает `pool.publication_odata`
- **AND** `poolops` executor/adapter не сконфигурирован
- **WHEN** runtime пытается исполнить operation node
- **THEN** node завершается ошибкой fail-closed
- **AND** workflow execution не получает успешный `completed` из-за `execution_skipped`

### Requirement: Runtime MUST fail-closed при pinned drift и неисполненном registry
Система ДОЛЖНА (SHALL) прекращать выполнение pool operation node при несоответствии pinned binding:
- exposure не найден;
- exposure неактивен/неопубликован;
- `template_exposure_revision` не совпал.

Система НЕ ДОЛЖНА (SHALL NOT) использовать fallback на `alias_latest` или legacy path.

#### Scenario: Drift revision останавливает node execution
- **GIVEN** node содержит `template_exposure_id=<id>` и `template_exposure_revision=12`
- **AND** текущий revision exposure равен `13`
- **WHEN** runtime исполняет node
- **THEN** execution завершается ошибкой drift
- **AND** код ошибки равен `TEMPLATE_DRIFT`
- **AND** side effects node не выполняются

### Requirement: Pool runtime MUST возвращать стабильные fail-closed коды ошибок
Система ДОЛЖНА (SHALL) возвращать machine-readable коды ошибок для несоответствий registry/binding/executor в compile/runtime path.

Канонический набор кодов:
- `POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED` — required alias не найден в registry.
- `POOL_RUNTIME_TEMPLATE_INACTIVE` — pinned exposure найден, но неактивен/непубликован.
- `TEMPLATE_DRIFT` — pinned revision не совпадает с текущей ревизией exposure.
- `POOL_RUNTIME_TEMPLATE_UNSUPPORTED_EXECUTOR` — executor pinned exposure не поддерживает `PoolDomainBackend`.
- `WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED` — workflow worker не сконфигурирован для исполнения `pool.*` operation nodes.
- `POOL_RUNTIME_ROUTE_DISABLED` — `poolops` route отключён runtime kill-switch и выполнение `pool.*` блокируется fail-closed.
- `POOL_RUNTIME_CONTEXT_MISMATCH` — bridge request содержит несогласованную tenant/run/execution/node связку.
- `IDEMPOTENCY_KEY_CONFLICT` — повторный bridge request использует тот же idempotency key, но другой request fingerprint.
- `POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED` — retry budget/deadline bridge-вызова исчерпан до успешного ответа.

Система ДОЛЖНА (SHALL) передавать fail-closed `error_code` по цепочке `worker -> internal workflows status update -> facade diagnostics` без деградации до неструктурированного текста.

#### Scenario: Inactive exposure блокирует исполнение node fail-closed
- **GIVEN** node содержит pinned `template_exposure_id=<id>` и `template_exposure_revision=<r>`
- **AND** exposure `<id>` существует, но помечен inactive
- **WHEN** runtime пытается исполнить node
- **THEN** node завершается fail-closed без выполнения side effects
- **AND** код ошибки равен `POOL_RUNTIME_TEMPLATE_INACTIVE`

#### Scenario: Pool operation в workflow worker без executor возвращает стабильный код ошибки
- **GIVEN** workflow worker обрабатывает operation node с `operation_type=pool.publication_odata`
- **AND** pool executor wiring отсутствует
- **WHEN** node исполняется
- **THEN** node завершается fail-closed
- **AND** ошибка содержит код `WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED`

#### Scenario: Fail-closed code сохраняется в execution diagnostics через internal status update
- **GIVEN** worker завершает execution со статусом `failed` и `error_code=WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED`
- **WHEN** worker вызывает internal `update-execution-status`
- **THEN** orchestrator сохраняет machine-readable `error_code` для execution
- **AND** pools facade возвращает тот же код в diagnostics/problem-details

#### Scenario: Отключённый poolops route возвращает стабильный fail-closed код
- **GIVEN** runtime kill-switch отключил `poolops` route
- **AND** worker обрабатывает operation node с `operation_type=pool.publication_odata`
- **WHEN** runtime выбирает execution path
- **THEN** node завершается fail-closed без выполнения side effects
- **AND** ошибка содержит код `POOL_RUNTIME_ROUTE_DISABLED`

### Requirement: Pool workflow runtime MUST переиспользовать definition и хранить immutable execution snapshot
Система ДОЛЖНА (SHALL) резолвить/создавать workflow template для pool run по `definition_key`, а не по run-specific fingerprint.

Система ДОЛЖНА (SHALL) сохранять для каждого workflow execution immutable snapshot, включающий:
- run-specific вход (`period_start`, `period_end`, `run_input`, `seed`);
- lineage metadata (`root_workflow_run_id`, `parent_workflow_run_id`, `attempt_number`, `attempt_kind`);
- provenance ссылки на definition (`workflow_template_id`, `workflow_template_version`, `definition_key`).

Retry path ДОЛЖЕН (SHALL) переиспользовать тот же definition (если структурный контекст не изменился) и создавать новый execution snapshot для новой попытки.

#### Scenario: Повторный run не создаёт новый template при неизменной структуре
- **GIVEN** существует workflow definition для (`pool_id`, `direction`, `mode`, template version, DAG structure)
- **WHEN** создаётся новый run с другим `period_*` или `run_input`
- **THEN** runtime переиспользует существующий workflow template
- **AND** создаёт новый workflow execution с новым snapshot

#### Scenario: Retry наследует definition и фиксирует новый lineage snapshot
- **GIVEN** run имеет root workflow execution и доступен для retry
- **WHEN** выполняется retry
- **THEN** retry execution ссылается на тот же `definition_key`
- **AND** snapshot содержит `attempt_kind=retry` и корректный `parent_workflow_run_id`

#### Scenario: Historical executions остаются читаемыми после split-модели
- **GIVEN** execution создан до введения definition reuse
- **WHEN** клиент читает details/provenance run
- **THEN** historical execution остаётся доступным
- **AND** отсутствие новых snapshot полей не приводит к ошибке десериализации

### Requirement: Workflow status updater MUST не синтезировать publication_step_state из агрегатного workflow status
Система ДОЛЖНА (SHALL) обновлять `publication_step_state` только на основании фактического исполнения publication-step (`pool.publication_odata`) и его доменного результата.

Система НЕ ДОЛЖНА (SHALL NOT) автоматически выставлять `publication_step_state=started|completed` только потому, что aggregate `workflow.status` перешёл в `running|completed`.

#### Scenario: Aggregate completed без publication-step не меняет publication_step_state на completed
- **GIVEN** workflow execution consumer `pools`
- **AND** aggregate статус execution перешёл в `completed`
- **AND** publication-step фактически не исполнялся
- **WHEN** runtime updater синхронизирует metadata
- **THEN** `publication_step_state` остаётся в прежнем фактическом значении
- **AND** система не создаёт ложный сигнал завершённой публикации

### Requirement: Poolops bridge MUST иметь детерминированный runtime-контракт
Система ДОЛЖНА (SHALL) использовать canonical bridge endpoint `POST /api/v2/internal/workflows/execute-pool-runtime-step` для pool runtime шагов, КРОМЕ `pool.publication_odata` после Big-bang cutover.

После Big-bang cutover шаг `pool.publication_odata` ДОЛЖЕН (SHALL) исполняться локально в worker через shared `odata-core`.

Bridge endpoint НЕ ДОЛЖЕН (SHALL NOT) выполнять OData side effects для `pool.publication_odata` после cutover и ДОЛЖЕН (SHALL) возвращать non-retryable конфликт с machine-readable кодом.

Fail-closed код для этого контракта ДОЛЖЕН (SHALL) быть стабильным: `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.

#### Scenario: publication_odata после cutover исполняется без bridge side effect
- **GIVEN** Big-bang cutover завершён
- **WHEN** worker исполняет шаг `pool.publication_odata`
- **THEN** OData запросы выполняются через worker `odata-core` без вызова bridge endpoint для side effect
- **AND** доменный lifecycle/projection pool run остаётся совместимым с контрактом

#### Scenario: Вызов bridge для publication_odata после cutover отклоняется fail-closed
- **GIVEN** после cutover отправлен bridge-запрос с `operation_type=pool.publication_odata`
- **WHEN** Orchestrator валидирует запрос
- **THEN** endpoint возвращает `409 Conflict` (non-retryable) с payload `ErrorResponse`
- **AND** поле `code` равно `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`
- **AND** side effects публикации не выполняются

### Requirement: Bridge/status update retry MUST иметь единственного владельца
Система ДОЛЖНА (SHALL) выполнять retry для `poolops` bridge и `update-execution-status` только в одном слое transport path.

Система НЕ ДОЛЖНА (SHALL NOT) применять stacked retry между workflow handler и HTTP client transport.

Система ДОЛЖНА (SHALL) считать transport client единственным retry-owner для bridge/status update вызовов.

Система ДОЛЖНА (SHALL) учитывать `Retry-After` при HTTP `429`, если заголовок присутствует.

Система ДОЛЖНА (SHALL) ограничивать retry budget дедлайном шага (`step timeout/deadline`) и НЕ ДОЛЖНА (SHALL NOT) делать retry после исчерпания бюджета.

При исчерпании retry budget система ДОЛЖНА (SHALL) завершать шаг fail-closed с кодом `POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED`.

#### Scenario: Временная ошибка не приводит к retry amplification
- **GIVEN** bridge/status update path получает временную ошибку `503`
- **WHEN** срабатывает retry policy
- **THEN** количество фактических HTTP попыток ограничено single retry-owner policy
- **AND** telemetry показывает один attempt counter без дублирующих retry-loop событий

#### Scenario: 429 с Retry-After уважает серверный backoff
- **GIVEN** bridge endpoint возвращает `429` с заголовком `Retry-After`
- **WHEN** transport client планирует следующую retry-попытку
- **THEN** retry выполняется не раньше интервала `Retry-After`
- **AND** попытка всё равно подчиняется общему retry budget

#### Scenario: Исчерпание retry budget завершает шаг fail-closed без дополнительных retry
- **GIVEN** шаг `pool.publication_odata` получает последовательность retryable ошибок
- **AND** суммарное время попыток достигло `step timeout/deadline`
- **WHEN** transport client оценивает следующую попытку
- **THEN** новая retry-попытка не выполняется
- **AND** шаг завершается с кодом `POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED`

### Requirement: Projection hardening rollout MUST быть staged для historical workflow_core run-ов
Система ДОЛЖНА (SHALL) применять staged migration для `workflow_core` execution с `publication_step_state=null`.

Система ДОЛЖНА (SHALL) использовать migration cutoff из runtime setting `pools.projection.publication_hardening_cutoff_utc` (RFC3339 UTC).

Система ДОЛЖНА (SHALL) вычислять `projection_timestamp` по формуле:
- `coalesce(workflow_execution.started_at, workflow_execution.created_at, pool_run.created_at)`.

Система ДОЛЖНА (SHALL) применять cutoff к `projection_timestamp`:
- historical execution (до cutoff) МОЖЕТ (MAY) использовать legacy fallback по `failed_targets`;
- execution начиная с cutoff НЕ ДОЛЖЕН (SHALL NOT) проецироваться в `published/partial_success` без `publication_step_state=completed`.

#### Scenario: Historical workflow_core execution до cutoff сохраняет legacy terminal projection
- **GIVEN** run имеет `execution_backend=workflow_core` и `workflow.status=completed`
- **AND** `publication_step_state` отсутствует
- **AND** execution относится к historical окну (до cutoff)
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад использует migration fallback по `failed_targets`
- **AND** historical run остаётся читаемым без forced перехода в `failed`

#### Scenario: Новый workflow_core execution после cutoff fail-closed при отсутствии publication completion
- **GIVEN** run имеет `execution_backend=workflow_core` и `workflow.status=completed`
- **AND** execution создан после cutoff
- **AND** `publication_step_state!=completed`
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает `failed`
- **AND** фасад НЕ возвращает `published` или `partial_success`

### Requirement: Projection fail-closed diagnostics MUST использовать стабильный внешний `code`
Система ДОЛЖНА (SHALL) проецировать внутренний `error_code` в внешний Problem Details `code` без изменения значения.

Система ДОЛЖНА (SHALL) использовать код `POOL_PUBLICATION_STEP_INCOMPLETE` для случая:
- `workflow.status=completed`;
- (`approval_required=false` ИЛИ `approved_at is not null`);
- `publication_step_state!=completed`.

#### Scenario: Completed workflow без completed publication-step возвращает стабильный code
- **GIVEN** pool run имеет `workflow.status=completed`
- **AND** publication-step не завершён (`publication_step_state!=completed`)
- **WHEN** facade формирует diagnostics/problem details
- **THEN** в Problem Details поле `code` равно `POOL_PUBLICATION_STEP_INCOMPLETE`
- **AND** код не деградирует в generic `VALIDATION_ERROR` или неструктурированный текст

### Requirement: Workflow execution diagnostics MUST хранить structured fail-closed поля
Система ДОЛЖНА (SHALL) сохранять в `WorkflowExecution` structured поля диагностики ошибок исполнения:
- `error_code` (machine-readable);
- `error_details` (optional JSON, без секретов);
- `error_message` (human-readable).

Система ДОЛЖНА (SHALL) принимать `error_code`/`error_details` в internal `update-execution-status` и сохранять их без потери значения.

Система ДОЛЖНА (SHALL) применять к `error_details` правила безопасности и объёма:
- allowlist schema для диагностических полей;
- ограничение размера persisted payload (max 8 KiB после сериализации);
- обязательная redaction секретов до сохранения и выдачи наружу.

#### Scenario: Internal status update сохраняет structured failure diagnostics
- **GIVEN** worker отправляет `update-execution-status` со статусом `failed`
- **AND** payload содержит `error_code=POOL_RUNTIME_ROUTE_DISABLED`
- **AND** payload содержит `error_details` с диагностическим контекстом без секретов
- **WHEN** orchestrator обрабатывает запрос
- **THEN** `WorkflowExecution` сохраняет `error_code`, `error_details`, `error_message`
- **AND** facade diagnostics использует тот же `error_code` в Problem Details поле `code`

#### Scenario: Опасные или слишком большие error_details санитизируются перед persistence
- **GIVEN** worker передаёт `error_details` c потенциально чувствительными полями или объёмом больше 8 KiB
- **WHEN** internal `update-execution-status` обрабатывает payload
- **THEN** Orchestrator применяет redaction и обрезку по лимиту
- **AND** в persistence/facade не попадают несанкционированные секреты

### Requirement: Poolops execution path MUST быть наблюдаемым
Система ДОЛЖНА (SHALL) публиковать наблюдаемые сигналы для `poolops` path:
- маршрутизация operation node в `poolops`;
- число retry bridge-вызова;
- коды fail-closed ошибок;
- latency bridge-вызовов.

Система ДОЛЖНА (SHALL) трассировать повторные HTTP-вызовы bridge с признаком resend attempt.

#### Scenario: Инцидент по publication_odata диагностируется через trace и метрики
- **GIVEN** `pool.publication_odata` завершился fail-closed ошибкой
- **WHEN** оператор анализирует telemetry
- **THEN** видны route decision в `poolops`, retry count и финальный machine-readable error code
- **AND** trace содержит атрибуты resend attempt для повторных bridge-запросов

### Requirement: Workflow runtime model MUST сохранять `operation_ref` для pool operation nodes
Система ДОЛЖНА (SHALL) сохранять и пробрасывать `operation_ref` в Go workflow runtime model и bridge payload для `pool.*` шагов.

Система НЕ ДОЛЖНА (SHALL NOT) деградировать `operation_ref` до `template_id`-only semantics для pinned runtime path.

#### Scenario: Pinned operation_ref проходит из DAG в bridge payload без потери полей
- **GIVEN** operation node содержит `operation_ref(binding_mode=pinned_exposure, template_exposure_id, template_exposure_revision)`
- **WHEN** worker исполняет шаг через `poolops` bridge
- **THEN** bridge payload содержит `operation_ref.alias`, `binding_mode`, `template_exposure_id`, `template_exposure_revision`
- **AND** runtime проверки drift/executor выполняются по переданному `operation_ref`

### Requirement: Poolops rollout MUST быть управляемым feature-flag/canary + kill-switch
Система ДОЛЖНА (SHALL) включать `poolops` route поэтапно через feature flag и canary rollout.

Система ДОЛЖНА (SHALL) иметь kill-switch для быстрого отключения `poolops` route без rollback схем данных.

Система НЕ ДОЛЖНА (SHALL NOT) возвращать `pool.*` execution в legacy silent-success маршрут при отключении `poolops` через kill-switch.

Система ДОЛЖНА (SHALL) иметь независимые runtime controls для:
- маршрутизации `poolops` execution path;
- projection hardening (`publication_hardening_cutoff_utc` и связанные правила).

Система ДОЛЖНА (SHALL) фиксировать route decision для execution при старте run (route-latching).

Система ДОЛЖНА (SHALL) применять kill-switch к новым execution, не меняя execution path уже запущенных run-ов.

#### Scenario: Kill-switch выключает poolops route без data rollback
- **GIVEN** `poolops` route включён и обнаружена регрессия в runtime
- **WHEN** оператор активирует kill-switch
- **THEN** новые `pool.*` operation nodes НЕ выполняются через legacy silent-success маршрут
- **AND** новые `pool.*` operation nodes завершаются fail-closed с machine-readable кодом
- **AND** исторические данные не изменяются

#### Scenario: In-flight run сохраняет ранее зафиксированный execution path после kill-switch
- **GIVEN** workflow run уже стартовал и route decision зафиксирован как `poolops`
- **WHEN** оператор активирует kill-switch во время выполнения этого run
- **THEN** текущий run продолжает выполнение по зафиксированному execution path
- **AND** kill-switch влияет только на новые run-ы

### Requirement: Publication workflow step MUST использовать shared `odata-core` transport в Big-bang режиме
Система ДОЛЖНА (SHALL) выполнять Big-bang перенос `pool.publication_odata` на shared `odata-core` синхронно с переключением `odataops`.

Переход на shared `odata-core` НЕ ДОЛЖЕН (SHALL NOT) менять доменные инварианты pool runtime:
- правила `approval_state/publication_step_state`;
- идемпотентность публикации;
- diagnostics contract публикации;
- retry policy ограничения (`max_attempts_total`, `retry_interval_seconds` caps).

#### Scenario: publication_odata сохраняет доменный контракт после Big-bang cutover
- **GIVEN** workflow run дошёл до шага `publication_odata`
- **WHEN** step исполняется через worker `odata-core`
- **THEN** run lifecycle и pool facade status projection остаются совместимыми с текущим контрактом
- **AND** publication diagnostics сохраняют каноническую структуру
- **AND** side effects публикации остаются идемпотентными

### Requirement: OData compatibility profile MUST оставаться source-of-truth для shared transport
Система ДОЛЖНА (SHALL) применять compatibility constraints из `odata-compatibility-profile` при исполнении `publication_odata` через worker `odata-core`.

#### Scenario: shared transport соблюдает compatibility ограничения
- **GIVEN** целевая ИБ требует конкретный write media-type из compatibility profile
- **WHEN** `publication_odata` исполняется через worker `odata-core`
- **THEN** запросы используют совместимый media-type
- **AND** при несовместимом профиле шаг завершается контролируемой fail-closed ошибкой

### Requirement: Publication diagnostics projection MUST оставаться совместимой для pools facade
Система ДОЛЖНА (SHALL) сохранять совместимость операторского read-model после переноса transport-owner:
- источник истины для `/api/v2/pools/runs/{run_id}/report` остаётся `PoolPublicationAttempt`;
- структура `publication_attempts`, `publication_summary` и `diagnostics` остаётся совместимой с текущим facade-контрактом.

#### Scenario: После cutover отчёт run сохраняет совместимую diagnostics структуру
- **GIVEN** публикация завершена после Big-bang cutover
- **WHEN** оператор запрашивает `/api/v2/pools/runs/{run_id}/report`
- **THEN** ответ содержит ожидаемые поля `publication_attempts`, `publication_summary`, `diagnostics`
- **AND** существующие клиенты не требуют миграции формата

### Requirement: Publication auth context MUST быть частью workflow runtime execution context
Система ДОЛЖНА (SHALL) формировать для `pool.publication_odata` явный `publication_auth` контекст в workflow execution:
- `strategy` (`actor|service`);
- `actor_username` (для `actor`);
- `source` (provenance инициатора publication attempt).

Система ДОЛЖНА (SHALL) прокидывать этот контекст от orchestrator runtime до worker operation node без потери данных.

#### Scenario: Safe confirm формирует actor publication context
- **GIVEN** safe run ожидает approval
- **AND** оператор вызывает `confirm-publication`
- **WHEN** publication step enqueue в workflow runtime
- **THEN** execution context содержит `publication_auth.strategy=actor`
- **AND** `publication_auth.actor_username` соответствует оператору, подтвердившему публикацию

#### Scenario: Retry publication фиксирует нового инициатора attempt
- **GIVEN** run в `partial_success` и оператор запускает retry
- **WHEN** создаётся новый publication attempt
- **THEN** новый execution context содержит актуальный `publication_auth` provenance
- **AND** worker использует этот context для credentials lookup

### Requirement: Publication auth context MUST валидироваться fail-closed до OData side effects
Система ДОЛЖНА (SHALL) fail-closed отклонять execution, если `publication_auth` неконсистентен:
- `strategy=actor`, но `actor_username` пустой;
- strategy неизвестна;
- context отсутствует для publication node.

#### Scenario: Неконсистентный publication_auth блокирует шаг до transport вызовов
- **GIVEN** workflow execution дошёл до `pool.publication_odata`
- **AND** `publication_auth` невалиден
- **WHEN** worker валидирует runtime context
- **THEN** шаг завершается fail-closed с machine-readable ошибкой
- **AND** OData side effect не выполняется

### Requirement: Publication provenance MUST отражать фактического инициатора safe/retry команды
Система ДОЛЖНА (SHALL) формировать `publication_auth.source` и `publication_auth.actor_username` от фактического инициатора команд `confirm-publication` и `retry`, если стратегия `actor`.

Система НЕ ДОЛЖНА (SHALL NOT) подменять actor provenance generic actor'ом (например, `workflow_engine`) в тех сценариях, где инициатор-оператор известен.

#### Scenario: Confirm от оператора сохраняет actor provenance без подмены
- **GIVEN** safe run находится в `awaiting_approval`
- **AND** оператор `alice` вызывает `confirm-publication`
- **WHEN** публикационный шаг enqueue в workflow runtime
- **THEN** execution context содержит `publication_auth.actor_username=alice`
- **AND** provenance не подменён техническим `workflow_engine`

### Requirement: Pool runtime MUST компилировать document plan перед publication step
Система ДОЛЖНА (SHALL) перед шагом `pool.publication_odata` формировать `document_plan_artifact` на основе runtime distribution artifact, active topology version и валидной `document_policy`.

Система ДОЛЖНА (SHALL) передавать в publication step только этот artifact как source-of-truth для create-run path.

#### Scenario: Publication step получает document plan из runtime compile
- **GIVEN** distribution шаги завершились успешно и policy валидна
- **WHEN** runtime переходит к pre-publication стадии
- **THEN** в execution context сохраняется `document_plan_artifact`
- **AND** publication step использует artifact вместо произвольного raw payload

### Requirement: Document plan compile MUST принимать distribution_artifact.v1 как обязательный upstream контракт
Система ДОЛЖНА (SHALL) выполнять compile `document_plan_artifact` только от валидного `distribution_artifact.v1`, сохраненного в execution context create-run path.

Система ДОЛЖНА (SHALL) валидировать минимальный обязательный набор полей `distribution_artifact.v1` перед downstream compile:
- `version`;
- `topology_version_ref`;
- `node_totals[]`;
- `edge_allocations[]`;
- `coverage`;
- `balance`;
- `input_provenance`.

Система НЕ ДОЛЖНА (SHALL NOT) использовать raw `run_input` как authoritative источник распределенных сумм для compile document plan.

#### Scenario: Compile document plan получает распределение только из runtime artifact
- **GIVEN** execution context содержит валидный `distribution_artifact.v1`
- **WHEN** runtime запускает compile `document_plan_artifact`
- **THEN** вход распределения берется из сохраненного artifact
- **AND** значения из raw `run_input` не используются как источник распределенных сумм

#### Scenario: Неполный upstream artifact блокирует compile document plan fail-closed
- **GIVEN** в execution context отсутствует `distribution_artifact.v1` или отсутствуют обязательные поля контракта
- **WHEN** runtime пытается выполнить compile `document_plan_artifact`
- **THEN** compile завершается fail-closed до publication step
- **AND** execution diagnostics содержит machine-readable код нарушения artifact-контракта

#### Scenario: Попытка bypass через raw run_input artifact-поля отклоняется
- **GIVEN** оператор/клиент передал в `run_input` поля, имитирующие runtime artifacts (`distribution_artifact`/`document_plan_artifact`/`pool_runtime_*`)
- **WHEN** create-run path формирует execution context и downstream compile вход
- **THEN** эти raw поля не используются как source-of-truth для compile
- **AND** downstream compile читает только валидный artifact из execution context contract key

### Requirement: Document plan artifact MUST публиковаться как downstream handoff контракт для atomic compiler
Система ДОЛЖНА (SHALL) сохранять `document_plan_artifact.v1` в execution context как downstream handoff-контракт для atomic workflow compiler из change `refactor-03-unify-platform-execution-runtime`.

Система НЕ ДОЛЖНА (SHALL NOT) требовать повторного policy compile на стороне atomic compiler, если валидный `document_plan_artifact.v1` уже сохранен.

#### Scenario: Downstream atomic compiler потребляет готовый document_plan_artifact.v1
- **GIVEN** runtime успешно сохранил `document_plan_artifact.v1` после compile policy
- **WHEN** atomic workflow compiler (Track B, `refactor-03`) строит execution graph
- **THEN** compiler использует сохраненный `document_plan_artifact.v1` как входной контракт
- **AND** повторная policy-компиляция в atomic compiler не выполняется

### Requirement: Runtime MUST блокировать publication fail-closed при policy compile errors
Система ДОЛЖНА (SHALL) завершать execution fail-closed до `pool.publication_odata`, если policy отсутствует там, где обязательна, policy невалидна, compile chain/mapping завершился ошибкой или нарушен required invoice rule.

#### Scenario: Ошибка compile policy блокирует переход к публикации
- **GIVEN** runtime не смог построить корректный `document_plan_artifact`
- **WHEN** выполняется transition к `pool.publication_odata`
- **THEN** publication step не запускается
- **AND** execution diagnostics содержит machine-readable policy error code

### Requirement: Retry path MUST использовать persisted document plan artifact
Система ДОЛЖНА (SHALL) при retry publication использовать persisted `document_plan_artifact` исходного run как базовый источник структуры документов и link rules.

Система НЕ ДОЛЖНА (SHALL NOT) требовать от оператора повторной передачи полного произвольного payload документов для восстановления chain semantics.

#### Scenario: Retry переиспользует persisted chain-план
- **GIVEN** run завершился `partial_success` и содержит persisted `document_plan_artifact`
- **WHEN** оператор инициирует retry failed targets
- **THEN** runtime формирует retry payload из persisted artifact
- **AND** успешные документы цепочки не дублируются

### Requirement: Pool workflow compiler MUST детализировать run до атомарных execution шагов
Система ДОЛЖНА (SHALL) компилировать `pool run` в атомарный workflow graph, где шаги отражают конкретные доменные действия по рёбрам/документам, а не только coarse-grained этапы.

Атомарный graph ДОЛЖЕН (SHALL) строиться из:
- distribution artifact (coverage + allocations);
- document plan artifact (document chains, field/table mappings, invoice rules).

Система ДОЛЖНА (SHALL) генерировать deterministic `node_id` для атомарных шагов на основе стабильных бизнес-ключей (`edge_id`, `document_role`, `action_kind`, `attempt_scope`).

#### Scenario: Pool run компилируется в per-edge/per-document workflow nodes
- **GIVEN** активная topology содержит несколько рёбер и document chain policy
- **WHEN** runtime компилирует execution plan для run
- **THEN** DAG содержит атомарные nodes по рёбрам и документам
- **AND** каждый node имеет стабильный deterministic `node_id`

### Requirement: Invoice-required policy MUST материализоваться отдельными атомарными шагами
Система ДОЛЖНА (SHALL) для policy с `invoice_mode=required` компилировать отдельные invoice nodes и link dependencies в execution graph.

Система НЕ ДОЛЖНА (SHALL NOT) считать публикацию завершённой, если обязательный invoice node отсутствует или завершился неуспешно.

#### Scenario: Required invoice формирует отдельный шаг и влияет на terminal projection
- **GIVEN** document chain требует связанную счёт-фактуру (`invoice_mode=required`)
- **WHEN** run выполняется через workflow runtime
- **THEN** invoice публикуется отдельным atomic node
- **AND** при его fail статус run не может перейти в `published`

### Requirement: Retry MUST работать по failed atomic nodes
Система ДОЛЖНА (SHALL) строить retry execution для `pool run` по подмножеству failed atomic nodes с учетом зависимостей, без повторного исполнения уже успешных атомарных шагов.

#### Scenario: Partial failure вызывает retry только проблемных атомарных шагов
- **GIVEN** run завершился с failed atomic nodes при части уже успешных шагов
- **WHEN** оператор инициирует retry
- **THEN** runtime формирует retry graph только для failed subset и необходимых зависимостей
- **AND** успешные шаги не исполняются повторно

### Requirement: Atomic compiler MUST использовать upstream artifact контракты без переопределения их семантики
Система ДОЛЖНА (SHALL) компилировать атомарный workflow graph, используя:
- `distribution_artifact.v1` как единственный source-of-truth распределённых сумм;
- `document_plan_artifact.v1` как единственный source-of-truth document chains и invoice rules.

Система НЕ ДОЛЖНА (SHALL NOT) переопределять формулы распределения или правила policy compile внутри atomic compiler.

#### Scenario: Atomic compiler потребляет готовые artifacts и не использует raw run_input для доменной семантики
- **GIVEN** run имеет сохранённые `distribution_artifact.v1` и `document_plan_artifact.v1`
- **WHEN** runtime компилирует атомарный workflow graph
- **THEN** node semantics формируются из этих artifacts
- **AND** raw `run_input` не используется для переопределения распределения/chain правил

### Requirement: Pool runtime distribution steps MUST использовать алгоритмический source-of-truth
Система ДОЛЖНА (SHALL) исполнять шаги `pool.distribution_calculation.top_down` и `pool.distribution_calculation.bottom_up` через канонические алгоритмы распределения/агрегации, а не через summary-only вычисления.

Система ДОЛЖНА (SHALL) сохранять результат этих шагов как детерминированный runtime artifact, который используется шагами `reconciliation_report` и `publication_odata`.

#### Scenario: Workflow runtime использует active topology version в distribution step
- **GIVEN** для пула существуют versioned узлы и рёбра
- **AND** run выполняется за конкретный период
- **WHEN** workflow runtime исполняет `distribution_calculation`
- **THEN** расчёт использует только topology-версию, активную на этот период
- **AND** результат сохраняется в execution context как структурированный artifact

### Requirement: Reconciliation MUST блокировать publication при нарушении distribution invariants
Система ДОЛЖНА (SHALL) завершать execution fail-closed до старта `pool.publication_odata`, если нарушены инварианты распределения:
- несходимость баланса;
- gaps покрытия активной цепочки publish-target узлов;
- отсутствие или неконсистентность required distribution artifact.

Система ДОЛЖНА (SHALL) возвращать machine-readable fail-closed код, который сохраняется в execution diagnostics и проецируется во внешний pools facade.

#### Scenario: Нарушение сходимости блокирует publication step
- **GIVEN** distribution/reconciliation обнаружили несходимость исходной суммы
- **WHEN** runtime оценивает переход к `pool.publication_odata`
- **THEN** публикационный шаг не запускается
- **AND** execution завершается fail-closed с machine-readable кодом
- **AND** facade diagnostics возвращает тот же код без деградации

#### Scenario: Coverage gap в активной цепочке блокирует publication step
- **GIVEN** distribution artifact не покрывает активный publish-target узел цепочки
- **WHEN** runtime выполняет reconciliation gate
- **THEN** run останавливается до publication
- **AND** оператор получает machine-readable diagnostics с причиной gap coverage

### Requirement: Distribution artifact MUST быть стабильным upstream контрактом для downstream compile слоёв
Система ДОЛЖНА (SHALL) формировать versioned `distribution_artifact`, пригодный для потребления downstream compile слоями (`document_plan_artifact`, atomic workflow graph compile) без повторного чтения/доверия к raw `run_input`.

Система НЕ ДОЛЖНА (SHALL NOT) допускать обход этого контракта в create-run path через произвольный raw payload.

Минимальный обязательный набор полей `distribution_artifact.v1`:
- `version`;
- `topology_version_ref`;
- `node_totals[]`;
- `edge_allocations[]`;
- `coverage`;
- `balance`;
- `input_provenance`.

#### Scenario: Downstream compile использует только distribution artifact как вход распределения
- **GIVEN** create-run distribution завершён и сохранён versioned `distribution_artifact`
- **WHEN** runtime переходит к downstream compile (document plan или atomic graph)
- **THEN** вход распределения берётся из `distribution_artifact`
- **AND** raw `run_input` не используется как authoritative источник распределённых сумм

#### Scenario: Runtime отклоняет неполный distribution artifact контракт
- **GIVEN** execution context содержит artifact без одного из обязательных полей `distribution_artifact.v1`
- **WHEN** runtime пытается выполнить downstream compile/reconciliation
- **THEN** run завершается fail-closed до publication
- **AND** diagnostics содержит machine-readable код нарушения artifact-контракта

### Requirement: Runtime MUST выполнять master-data gate до `pool.publication_odata`
Система ДОЛЖНА (SHALL) перед запуском шага `pool.publication_odata` выполнять обязательный pre-publication gate:
1. извлечь ссылки на master-data из `document_plan_artifact`;
2. выполнить `resolve+upsert` этих сущностей в каждой target ИБ через canonical hub;
3. сохранить результат как `master_data_binding_artifact`;
4. только после успешного gate разрешить переход к `pool.publication_odata`.

Система НЕ ДОЛЖНА (SHALL NOT) запускать публикационный шаг, если master-data gate завершился ошибкой.

#### Scenario: Успешный master-data gate разрешает publication transition
- **GIVEN** `document_plan_artifact` валиден и master-data resolve/sync успешен по всем target ИБ
- **WHEN** runtime выполняет pre-publication sequence
- **THEN** в execution context сохраняется `master_data_binding_artifact_ref`
- **AND** run переходит к `pool.publication_odata`

#### Scenario: Ошибка master-data gate блокирует publication transition
- **GIVEN** хотя бы одна target ИБ вернула conflict/ambiguous результат resolve/sync
- **WHEN** runtime оценивает переход к `pool.publication_odata`
- **THEN** publication step не запускается
- **AND** execution завершается fail-closed с machine-readable master-data error code

### Requirement: Retry MUST переиспользовать immutable `master_data_snapshot_ref`
Система ДОЛЖНА (SHALL) фиксировать на create-run immutable `master_data_snapshot_ref`, который используется для resolve/sync и публикации.

Система ДОЛЖНА (SHALL) при retry использовать тот же `master_data_snapshot_ref` исходного run, чтобы исключить drift master-data между попытками в рамках одного run lineage.

#### Scenario: Retry публикации использует тот же snapshot master-data
- **GIVEN** исходный run уже сохранил `master_data_snapshot_ref`
- **WHEN** оператор запускает retry failed publication
- **THEN** runtime использует тот же `master_data_snapshot_ref`
- **AND** не подменяет snapshot на более новый без отдельного нового run

### Requirement: Pools facade MUST возвращать стабильный `master_data_gate` read-model для run inspection
Система ДОЛЖНА (SHALL) возвращать в `GET /api/v2/pools/runs/{run_id}` и `GET /api/v2/pools/runs/{run_id}/report` стабилизированный блок `master_data_gate`, достаточный для operator-facing диагностики.

Блок `master_data_gate` ДОЛЖЕН (SHALL) находиться внутри `run` payload (`run.master_data_gate`) в обоих endpoint-ах.

Минимальный состав блока:
- `status` (`completed|failed|skipped`);
- `mode` (`resolve_upsert`);
- `targets_count`;
- `bindings_count`;
- `error_code` (optional);
- `detail` (optional);
- `diagnostic` (optional structured object).

Для historical run-ов без шага `master_data_gate` система МОЖЕТ (MAY) возвращать `null`.

#### Scenario: Успешный run возвращает summary master-data gate
- **GIVEN** workflow execution выполнил шаг `pool.master_data_gate` успешно
- **WHEN** клиент запрашивает run details/report через facade
- **THEN** ответ содержит `master_data_gate.status=completed`
- **AND** содержит `targets_count` и `bindings_count` из execution context

#### Scenario: Fail-closed gate возвращает structured diagnostic
- **GIVEN** `pool.master_data_gate` завершился ошибкой
- **WHEN** клиент запрашивает run details/report через facade
- **THEN** ответ содержит `master_data_gate.status=failed` и machine-readable `error_code`
- **AND** поле `diagnostic` содержит structured контекст для remediation

#### Scenario: Неконсистентный gate feature flag блокирует публикацию fail-closed
- **GIVEN** effective runtime value `pools.master_data.gate_enabled` неконсистентен и не приводится к bool
- **WHEN** workflow выполняет `pool.master_data_gate`
- **THEN** шаг завершается fail-closed с machine-readable `error_code=MASTER_DATA_GATE_CONFIG_INVALID`
- **AND** side effects публикации в OData не выполняются

### Requirement: Publication attempts projection MUST агрегировать результаты всех atomic `publication_odata` nodes
Workflow status updater MUST строить attempts read-model не из первого найденного publication payload, а из полного набора atomic publication nodes текущего execution.

#### Scenario: Run report включает попытки из всех publication_odata узлов
- **GIVEN** workflow execution содержит несколько atomic publication nodes
- **WHEN** status updater проецирует attempts в run read-model
- **THEN** `pool_publication_attempts` отражает совокупность всех узлов текущего execution
- **AND** UI report не теряет успешные и failed attempts из отдельных atomic шагов

### Requirement: Run inspection read-model MUST включать readiness и verification статусы в стабильной структуре
Pools facade MUST возвращать в run/report детерминированные поля `readiness_blockers`, `verification_status` и `verification_summary`, чтобы оператор мог пройти весь процесс без анализа внутренних payload.

#### Scenario: Оператор получает единый прозрачный статус run
- **GIVEN** run прошёл readiness preflight и post-run verification
- **WHEN** оператор запрашивает run report
- **THEN** ответ содержит стабильную структуру readiness и verification полей
- **AND** отсутствие данных возвращается как явное состояние (`not_ready`/`not_verified`), а не молчаливый пропуск

