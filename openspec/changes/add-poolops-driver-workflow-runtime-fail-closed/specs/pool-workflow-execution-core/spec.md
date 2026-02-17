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
Система ДОЛЖНА (SHALL) исполнять bridge-вызовы `poolops` в Orchestrator domain runtime через внутренний аутентифицированный контракт с явными правилами:
- обязательный internal auth;
- передача tenant-scoped контекста (`tenant_id`, `pool_run_id`, `workflow_execution_id`, `node_id`);
- передача pinned binding provenance (`operation_ref.binding_mode`, `template_exposure_id`, `template_exposure_revision`);
- bounded timeout;
- retry только для retryable ошибок (transport/`5xx`/`429`) с exponential backoff и jitter;
- идемпотентный ключ шага (`workflow_execution_id + node_id + attempt`).

#### Scenario: Повтор bridge-вызова publication шага не создаёт дублирующий side effect
- **GIVEN** worker повторно отправляет bridge-вызов для того же шага `pool.publication_odata` (тот же `workflow_execution_id`, `node_id`, `attempt`)
- **WHEN** Orchestrator получает повторный запрос с тем же step-idempotency key
- **THEN** side effect публикации не дублируется
- **AND** worker получает детерминированный ответ по исходной попытке

#### Scenario: Bridge request несёт pinned provenance для deterministic runtime-проверок
- **GIVEN** worker исполняет `pool.prepare_input` через `binding_mode=pinned_exposure`
- **WHEN** формируется bridge-запрос в Orchestrator runtime
- **THEN** запрос содержит `template_exposure_id` и `template_exposure_revision`
- **AND** runtime не выполняет alias/fallback путь при несоответствии pinned binding

### Requirement: Projection hardening rollout MUST быть staged для historical workflow_core run-ов
Система ДОЛЖНА (SHALL) применять staged migration для `workflow_core` execution с `publication_step_state=null`.

Система ДОЛЖНА (SHALL) использовать migration cutoff:
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
