## MODIFIED Requirements
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

## ADDED Requirements
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
Система ДОЛЖНА (SHALL) исполнять bridge-вызовы `poolops` в Orchestrator domain runtime через canonical internal API endpoint `POST /api/v2/internal/workflows/execute-pool-runtime-step`, описанный в `contracts/orchestrator-internal/openapi.yaml`.

Система ДОЛЖНА (SHALL) применять для endpoint детерминированный контракт:
- обязательный internal auth;
- request schema с tenant-scoped контекстом (`tenant_id`, `pool_run_id`, `workflow_execution_id`, `node_id`, `operation_type`);
- обязательная передача pinned binding provenance (`operation_ref.alias`, `operation_ref.binding_mode`, `operation_ref.template_exposure_id`, `operation_ref.template_exposure_revision`);
- bounded timeout;
- идемпотентный ключ шага (`workflow_execution_id + node_id + step_attempt`).

Система ДОЛЖНА (SHALL) различать:
- `step_attempt` (уровень workflow runtime retry semantics);
- `transport_attempt` (повтор HTTP-запроса в рамках того же `step_attempt`).

Система ДОЛЖНА (SHALL) переиспользовать один и тот же step-idempotency key для всех `transport_attempt` внутри одного `step_attempt`.

Система ДОЛЖНА (SHALL) иметь явную status-matrix retry classification:
- retryable: transport errors, HTTP `429`, HTTP `5xx`;
- non-retryable: HTTP `400`, `401`, `404`, `409`.

Система ДОЛЖНА (SHALL) валидировать tenant-scoped bridge-контекст на стороне Orchestrator:
- `tenant_id` в request ДОЛЖЕН (SHALL) совпадать с tenant execution/run;
- `pool_run_id` ДОЛЖЕН (SHALL) быть связан с `workflow_execution_id`;
- `node_id` ДОЛЖЕН (SHALL) соответствовать исполняемому workflow step.

Система ДОЛЖНА (SHALL) считать idempotency key конфликтом случай, когда:
- key уже сохранён;
- новый request имеет другой fingerprint (body/context/provenance).

При idempotency key конфликте система ДОЛЖНА (SHALL):
- вернуть non-retryable `409 Conflict`;
- вернуть `error_code=IDEMPOTENCY_KEY_CONFLICT`;
- не выполнять side effects.

#### Scenario: Повтор bridge-вызова publication шага не создаёт дублирующий side effect
- **GIVEN** worker повторно отправляет bridge-вызов для того же шага `pool.publication_odata` (тот же `workflow_execution_id`, `node_id`, `step_attempt`)
- **WHEN** Orchestrator получает повторный запрос с тем же step-idempotency key
- **THEN** side effect публикации не дублируется
- **AND** worker получает детерминированный ответ по исходной попытке

#### Scenario: Transport retry в пределах step_attempt использует тот же idempotency key
- **GIVEN** шаг `pool.publication_odata` выполняется с `step_attempt=2`
- **AND** первый HTTP-вызов завершился retryable ошибкой `503`
- **WHEN** transport слой делает повторный HTTP-вызов для того же шага
- **THEN** повторный запрос использует тот же step-idempotency key
- **AND** новый idempotency key НЕ создаётся до перехода к следующему `step_attempt`

#### Scenario: Повтор с тем же idempotency key и другим payload завершается конфликтом
- **GIVEN** bridge-запрос для шага уже сохранён по step-idempotency key
- **AND** новый запрос с тем же key имеет другой request fingerprint
- **WHEN** Orchestrator получает повторный запрос
- **THEN** Orchestrator возвращает `409 Conflict` без выполнения side effects
- **AND** ответ содержит `error_code=IDEMPOTENCY_KEY_CONFLICT`

#### Scenario: Tenant/run/execution mismatch блокируется fail-closed
- **GIVEN** bridge-запрос содержит `tenant_id`, `pool_run_id`, `workflow_execution_id`, `node_id`
- **AND** хотя бы одно соответствие контекста невалидно
- **WHEN** Orchestrator валидирует bridge request
- **THEN** Orchestrator возвращает non-retryable `409 Conflict` без выполнения side effects
- **AND** ответ содержит `error_code=POOL_RUNTIME_CONTEXT_MISMATCH`

#### Scenario: Bridge request несёт pinned provenance для deterministic runtime-проверок
- **GIVEN** worker исполняет `pool.prepare_input` через `binding_mode=pinned_exposure`
- **WHEN** формируется bridge-запрос в Orchestrator runtime
- **THEN** запрос содержит `template_exposure_id` и `template_exposure_revision`
- **AND** runtime не выполняет alias/fallback путь при несоответствии pinned binding

#### Scenario: Non-retryable конфликт bridge endpoint не ретраится
- **GIVEN** Orchestrator bridge endpoint возвращает `409 Conflict` для шага `pool.approval_gate`
- **WHEN** worker обрабатывает ответ bridge-вызова
- **THEN** шаг завершается fail-closed без повторной отправки этого запроса
- **AND** итоговая ошибка содержит machine-readable код причины

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
