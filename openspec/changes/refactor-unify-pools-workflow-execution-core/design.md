## Context
Целевой поток для pools должен использовать единый execution stack (`workflows` + worker queue + audit/provenance), а не развивать второй runtime в `intercompany_pools`.

После разделения scope с `add-intercompany-pool-distribution-module` в этом change обязаны быть закрыты все runtime-решения: lifecycle, status projection, retry orchestration, provenance, tenant boundary и migration compatibility.

## Goals / Non-Goals
- Goals:
  - Один runtime исполнения для pools через `templates/workflow`.
  - Детерминированная status projection, включая `safe/unsafe` approval gate.
  - Явная tenant-изоляция `pool_run <-> workflow_run` без поломки legacy consumers.
  - Единый retry, OData identity и diagnostics контракт для API/UI.
  - Единый source-of-truth для runtime-семантики между change-ами.
- Non-Goals:
  - Big-bang удаление `workflows`.
  - Перепроектирование доменной математики top-down/bottom-up.
  - Введение отдельной queue-инфраструктуры для pools в phase 1.

## Terms
- `PoolSchemaTemplate`: foundation-название публичного XLSX/JSON шаблона импорта (`add-intercompany-pool-distribution-module`).
- `PoolImportSchemaTemplate`: execution-core термин для той же сущности, что `PoolSchemaTemplate` (алиас без нового публичного контракта).
- `workflow_binding`: optional metadata на import template из foundation-change; в unified runtime используется только как hint для compiler.
- `PoolExecutionPlan`: скомпилированный workflow-compatible graph для конкретного run-контекста.
- `approval_state`: техническая фаза safe-flow (`not_required`, `preparing`, `awaiting_approval`, `approved`), используемая для детерминированной проекции статуса.
- `publication_step_state`: runtime-флаг шага `publication_odata` (`not_enqueued`, `queued`, `started`, `completed`), используемый как primary сигнал для перехода `validated/queued -> publishing`.
- `status_reason`: подстатус facade-модели только для `validated` (`preparing`, `awaiting_approval`, `queued`); для остальных статусов `null`.
- `terminal_reason`: причина terminal-status для facade (`completed`, `failed_runtime`, `aborted_by_operator`), используется для детерминированной матрицы повторных safe-команд.

## Decisions
- Decision: `workflows` является execution-core для `pools`.
- Decision: source-of-truth для runtime-семантики `pools/runs*` задаётся этим change; `add-intercompany-pool-distribution-module` остаётся source-of-truth для foundation/domain vocabulary.
- Decision: терминология разделяется:
  - `PoolImportSchemaTemplate` не тождественен `WorkflowTemplate`;
  - `workflow_binding` на template сохраняется как optional compatibility hint для compiler и не является runtime source-of-truth;
  - compiler создаёт `PoolExecutionPlan` детерминированно из `pool_id + period + direction + source_hash + template_version`.
- Decision: `safe/unsafe` реализуются внутри workflow runtime, без второго оркестратора:
  - `safe`: workflow run создаётся с `approval_required=true`, `approval_state=preparing`; pre-publish шаги (`prepare_input`, `distribution_calculation`, `reconciliation_report`) выполняются до ручного решения оператора; после завершения pre-publish run переходит в `approval_state=awaiting_approval`;
  - в `safe` режиме только `publication_odata` блокируется до `confirm-publication`;
  - `unsafe`: `approval_state=not_required`, `approved_at` проставляется автоматически на create/start path;
  - явные команды фасада: `confirm-publication` и `abort-publication`.
- Decision: `approval_state` является runtime source-of-truth:
  - хранится в metadata workflow execution;
  - участвует в status projection как обязательный input;
  - возвращается в `GET /api/v2/pools/runs/{run_id}` для unified execution (legacy: `null`).
- Decision: status projection использует primary runtime-сигналы:
  - primary: `approval_state`, `approved_at`, `publication_step_state`;
  - secondary: `workflow.status` (используется только как вспомогательный индикатор очереди/terminal).
- Decision: canonical status mapping фиксируется и обязателен для API:
  - `draft` — run создан, workflow run ещё не создан;
  - `validated` + `status_reason=preparing` — `approval_required=true`, `approved_at is null`, `approval_state=preparing` (допустим `workflow.status in {pending, running}`);
  - `validated` + `status_reason=awaiting_approval` — `approval_required=true`, `approved_at is null`, `approval_state=awaiting_approval`;
  - `validated` + `status_reason=queued` — `publication_step_state in {not_enqueued, queued}`, `approval_required=false` или `approved_at is not null`;
  - `publishing` — `publication_step_state=started`, `approval_required=false` или `approved_at is not null`;
  - `published` — `workflow.status=completed` и `failed_targets=0`;
  - `partial_success` — `workflow.status=completed` и `failed_targets>0`;
  - `failed` — `workflow.status in {failed, cancelled}`.
- Decision: tenant boundary обязателен:
  - `WorkflowExecution` получает поля `tenant_id` и `execution_consumer`;
  - для `execution_consumer=pools` `tenant_id` обязателен;
  - `pool_run.tenant_id == workflow_execution.tenant_id` проверяется на create/read/retry path;
  - cross-tenant доступ к workflow provenance запрещён.
- Decision: идемпотентность `pool` домена сохраняется и прокидывается в workflow metadata/idempotency.
- Decision: retry-контракт фиксируется полностью:
  - `max_attempts_total=5` (включая initial attempt), эквивалентно foundation-контракту `max_attempts=5`;
  - `retry_interval_seconds` конфигурируем (`run override > template default > system default`);
  - эффективный интервал ограничен 120 секундами.
- Decision: provenance/retry lineage фиксируется явно:
  - `workflow_run_id` в facade указывает на root workflow execution chain (первая попытка);
  - `workflow_status` отражает активную попытку (последний элемент `retry_chain`);
  - `retry_chain` для unified execution всегда содержит минимум initial attempt и далее retry-attempts с parent linkage;
  - для legacy/historical run `retry_chain` может быть пустым.
- Decision: queueing phase 1 фиксируется:
  - stream: `commands:worker:workflows`;
  - execution priority: `normal` по умолчанию;
  - в `safe` режиме enqueue publication step происходит только после подтверждения.
- Decision: publication service (OData) исполняется только как adapter шага workflow graph.
- Decision: внешний идентификатор документа фиксируется strategy-based resolver:
  - primary: стабильный GUID (`_IDRRef` или `Ref_Key`);
  - fallback: `ExternalRunKey` (`runkey-<sha256[:32]>` от `run_id + target_database_id + document_kind + period`);
  - выбранная стратегия и identifier пишутся в audit/provenance.
- Decision: диагностический контракт публикации фиксирован и обязателен для API/UI:
  - `target_database_id`,
  - `payload_summary`,
  - `http_error`/`transport_error`,
  - `domain_error_code`,
  - `domain_error_message`,
  - `attempt_number`,
  - `attempt_timestamp`.
- Decision: `pools/runs*` остаётся доменным API-слоем и хранит reference на workflow run + provenance block.
- Decision: команды safe-mode имеют явную conflict-модель:
  - команды применимы только к safe-run (`approval_required=true`); для `unsafe` (`approval_state=not_required`) возвращается business conflict;
  - команды требуют `Idempotency-Key` header; key scope: `(run_id, command_type, idempotency_key)`;
  - повтор с тем же ключом возвращает сохранённый deterministic response (`202` или `200`) без side effects;
  - reuse ключа с несовместимым command payload/state-class возвращает `409` (`conflict_reason=idempotency_key_reused`);
  - семантическая идемпотентность = no side effects + no duplicate enqueue; response class определяется state-matrix;
  - `confirm-publication` допустим только из `approval_state=awaiting_approval`;
  - повторный `confirm-publication` в facade-состояниях `validated/queued` или `publishing` возвращает idempotent no-op;
  - `abort-publication` допустим только до старта шага `publication_odata`;
  - повторный `abort-publication` допустим как idempotent no-op только при `terminal_reason=aborted_by_operator`;
  - во всех остальных terminal/non-eligible состояниях команды возвращают business conflict.
- Decision: для safe-command processing и cutover атомарности выбран Variant A (предпочтительный):
  - канонический путь: transactional command log + transactional outbox в PostgreSQL;
  - один API-вызов (`confirm-publication`/`abort-publication`) в рамках одной транзакции ДОЛЖЕН:
    - валидировать state-matrix,
    - выполнить single-winner CAS-переход по (`approval_state`, `publication_step_state`, `terminal_reason`),
    - записать command outcome snapshot,
    - записать outbox-событие enqueue/cancel (если применимо);
  - публикация в Redis stream выполняется только outbox-dispatcher после commit;
  - fallback Variant B (Redis-only dedupe/lock без command log/outbox) отклонён для этого change.
- Decision: tenant confidentiality enforced на внешнем API:
  - cross-tenant и unknown `run_id` возвращают неразличимый внешний результат (`404 RUN_NOT_FOUND`);
  - причина `cross_tenant` фиксируется только во внутреннем audit/security логе.
- Decision: safe-команды имеют явный HTTP-контракт:
  - отсутствие `Idempotency-Key` -> `400 Bad Request`;
  - `confirm-publication` (`approval_state=awaiting_approval`) -> `202 Accepted`;
  - `confirm-publication` idempotent replay (`validated/queued|publishing`) -> `200 OK`;
  - `abort-publication` до старта `publication_odata` -> `202 Accepted`;
  - `abort-publication` idempotent replay (`terminal_reason=aborted_by_operator`) -> `200 OK`;
  - invalid command-state или reuse ключа с несовместимой семантикой -> `409 Conflict` с каноническим error payload.
- Decision: для historical/legacy runs без workflow-link возвращается совместимый provenance:
  - `workflow_run_id=null`,
  - `workflow_status=null`,
  - `execution_backend=legacy_pool_runtime`,
  - `retry_chain=[]`,
  - `legacy_reference` при наличии.
- Decision: удаление `workflows` запрещено до preflight-проверки consumer registry:
  - owner: platform team;
  - source-of-truth: `openspec/changes/refactor-unify-pools-workflow-execution-core/execution-consumers-registry.yaml` с валидацией по `execution-consumers-registry.schema.yaml`;
  - decommission разрешён только когда все consumers помечены `migrated=true`.
- Decision: machine-readable external dependency gate:
  - source-of-truth OData profile: `openspec/changes/refactor-unify-pools-workflow-execution-core/odata-compatibility-profile.yaml`;
  - human-readable `odata-compatibility-profile.md` поддерживается как проекция;
  - CI preflight валидирует profile и registry schema перед rollout/decommission.

## Architecture Invariants (Anti-Drift)
- Invariant 1: `workflows` остаётся единственным runtime для `pools`; второй lifecycle в `intercompany_pools` запрещён.
- Invariant 2: при `approval_required=true` и `approved_at is null` facade НЕ может возвращать `pool:publishing`.
- Invariant 3: `safe` run проходит фазы `approval_state=preparing -> awaiting_approval -> approved`; `unsafe` использует `approval_state=not_required`.
- Invariant 4: `status_reason` разрешён только для `pool:validated` и ограничен `preparing|awaiting_approval|queued`.
- Invariant 5: `abort-publication` после старта шага `publication_odata` всегда возвращает business conflict.
- Invariant 6: runtime endpoint retry фиксирован как `POST /api/v2/pools/runs/{run_id}/retry`.
- Invariant 7: `PoolImportSchemaTemplate` трактуется как execution-core алиас foundation `PoolSchemaTemplate`, без нового публичного артефакта.
- Invariant 8: при конфликте формулировок runtime приоритет имеет `pool-workflow-execution-core/spec.md`; foundation change используется только как domain vocabulary.
- Invariant 9: `approval_state` хранится как runtime source-of-truth в workflow metadata и возвращается facade API для unified execution.
- Invariant 10: state-matrix для `confirm/abort` не может оставаться неявной или частичной.
- Invariant 11: `409 Conflict` для safe-команд возвращает канонический error payload (`error_code`, `error_message`, `conflict_reason`, `retryable`, `run_id`).
- Invariant 12: preflight rollout шага `publication_odata` обязан валидировать совместимость compatibility mode целевой ИБ и media-type policy из `odata-compatibility-profile.yaml`; для legacy mode (`<=8.3.7`) без отдельной approved записи rollout блокируется (`No-Go`).
- Invariant 13: `publication_step_state` и `approval_state` имеют приоритет над `workflow.status` при проекции facade-статусов.
- Invariant 14: cross-tenant и unknown `run_id` во внешнем API неразличимы (`404 RUN_NOT_FOUND`).
- Invariant 15: safe-команды без `Idempotency-Key` отклоняются как `400`, а reuse ключа с несовместимой семантикой — как `409`.
- Invariant 16: safe-команды (`confirm/abort`) выполняются только через Variant A pipeline `command_log + outbox`; direct enqueue из HTTP path запрещён.
- Invariant 17: enqueue/cancel side effects для safe-команд допустимы только после commit транзакции, в которой записан command outcome snapshot.
- Invariant 18: конкурентные `confirm-publication` и `abort-publication` на одном run разрешаются детерминированно через single-winner CAS; проигравшая команда не создаёт side effects.

## Change Synchronization Rule
- Любая правка runtime-семантики в этом change ДОЛЖНА обновлять в одном коммите:
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/proposal.md`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/design.md`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/tasks.md`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/specs/pool-workflow-execution-core/spec.md`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/execution-consumers-registry.yaml`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/odata-compatibility-profile.yaml`

## Status Projection Contract
- `draft`: pool run существует, workflow run ещё не создан.
- `validated/preparing`: pre-publish шаги ещё выполняются или ставятся в очередь до точки ручного решения.
- `validated/awaiting_approval`: workflow run создан, ожидает явного решения пользователя.
- `validated/queued`: workflow run готов к исполнению и находится в очереди.
- `publishing`: шаг `publication_odata` помечен как started и выполняется после автоматического или ручного подтверждения.
- `published`: завершено без failed targets.
- `partial_success`: завершено с failed targets.
- `failed`: workflow завершился `failed` или `cancelled` (включая `abort-publication`).
- `status_reason`: применяется только для `validated`; допустимые значения `preparing|awaiting_approval|queued`.
- Для остальных facade-статусов `status_reason` возвращается `null`.
- Primary inputs проекции: `approval_state`, `approved_at`, `publication_step_state`; `workflow.status` используется как secondary terminal/queue indicator.

## Execution Mapping (Target)
- `PoolImportSchemaTemplate` + run context -> compiler -> `PoolExecutionPlan` -> `WorkflowTemplate`.
- `workflow_binding` (если присутствует) используется только как optional compiler hint.
- `PoolRun(start)`:
  - `unsafe`: create workflow run + auto-approval + enqueue;
  - `safe`: create workflow run (`approval_required=true`, `approval_state=preparing`), выполнить pre-publish шаги, перейти в `approval_state=awaiting_approval`, затем ждать confirm/abort; `publication_odata` enqueue только после confirm command.
- Workflow steps:
  - `prepare_input` (source/template validation),
  - `distribution_calculation` (top-down/bottom-up),
  - `reconciliation_report` (balance checks + artifacts),
  - `approval_gate` (safe only; resume by `confirm-publication`),
  - `publication_odata` (document upsert + posting).

## Provenance Contract (API)
- Базовые поля (всегда присутствуют в payload):
  - `workflow_run_id` (nullable; root execution chain id),
  - `workflow_status` (nullable; статус active attempt),
  - `approval_state` (nullable; mandatory for unified execution),
  - `terminal_reason` (nullable; mandatory for terminal unified execution),
  - `execution_backend` (`workflow_core` | `legacy_pool_runtime`),
  - `retry_chain` (array; для unified всегда содержит минимум initial attempt).
- Элемент `retry_chain[]`:
  - `workflow_run_id`,
  - `parent_workflow_run_id` (nullable для initial attempt),
  - `attempt_number`,
  - `attempt_kind` (`initial` | `retry`),
  - `status`.
- Для unified execution дополнительно обязательны:
  - `publication_identity_strategy`,
  - `publication_external_document_id`,
  - `publication_attempts[]` с каноническими diagnostic fields.
- Для historical/legacy execution дополнительно допустимы:
  - `legacy_reference` (nullable),
  - `retry_chain=[]`.

## Facade Commands Contract
- `POST /api/v2/pools/runs/{run_id}/confirm-publication`:
  - обязательный header: `Idempotency-Key`;
  - допустим из `approval_state=awaiting_approval`, переводит run в `queued`/`publishing`;
  - повторный вызов в facade-состояниях `validated/queued` или `publishing` идемпотентен и не создаёт duplicate enqueue;
  - в `approval_state=preparing|not_required` и terminal-состояниях возвращает business conflict.
- `POST /api/v2/pools/runs/{run_id}/abort-publication`:
  - обязательный header: `Idempotency-Key`;
  - завершает run как `failed` через workflow `cancelled`, если `publication_odata` ещё не начат;
  - повторный вызов идемпотентен только если `terminal_reason=aborted_by_operator`.
- Для terminal run команды confirm/abort возвращают business conflict, кроме idempotent-replay случая `abort-publication` при `terminal_reason=aborted_by_operator`.
- Для run, где уже начат `publication_odata`, `abort-publication` возвращает business conflict без изменения состояния.
- Cross-tenant и unknown `run_id` для `confirm/abort` возвращают одинаковый `404 RUN_NOT_FOUND` без утечки причины во внешний payload.

## Command State-Matrix
- Общая precondition для `confirm-publication` и `abort-publication`:
  - header `Idempotency-Key` обязателен, при отсутствии -> `400 Bad Request`.
- `confirm-publication`:
  - `approval_state=awaiting_approval` и facade `validated/awaiting_approval`: `202 Accepted`, enqueue publication.
  - `approval_state=approved` и facade `validated/queued|publishing`: `200 OK`, idempotent no-op.
  - `approval_state in {preparing,not_required}`: `409` business conflict.
  - terminal states: `409` business conflict.
- `abort-publication`:
  - `approval_required=true` + facade `validated/preparing|validated/awaiting_approval|validated/queued` и `publication_odata` not started: `202 Accepted`, cancel execution.
  - `approval_state=not_required` (`unsafe`): `409` business conflict.
  - `publication_odata` started: `409` business conflict.
  - terminal + `terminal_reason=aborted_by_operator`: `200 OK`, idempotent no-op.
  - остальные terminal states: `409` business conflict.

## Command Error Model (409 Conflict)
- OpenAPI response schema для `confirm-publication` / `abort-publication`:
  - `error_code` (string, stable machine code),
  - `error_message` (string, human-readable),
  - `conflict_reason` (enum: `not_safe_run`, `awaiting_pre_publish`, `publication_started`, `terminal_state`, `idempotency_key_reused`),
  - `retryable` (boolean),
  - `run_id` (string/uuid).

## External Dependency Gate
- Unified publication rollout в production разрешён только после фиксации OData compatibility profile (source-of-truth: `openspec/changes/refactor-unify-pools-workflow-execution-core/odata-compatibility-profile.yaml`):
  - список поддерживаемых endpoint/posting fields на конфигурацию 1С;
  - документированная стратегия fallback на `ExternalRunKey`;
  - подтверждённая верификация profile (`verification_status=approved`) для каждой целевой конфигурации;
  - release-артефакт фиксирует конкретную `profile_version`.
- CI preflight валидирует `odata-compatibility-profile.yaml` по schema и блокирует rollout при невалидной структуре.

## Decommission Preflight Contract
- Перед любым `workflows` decommission запускается preflight:
  - читает `execution-consumers-registry.yaml`,
  - валидирует структуру по `execution-consumers-registry.schema.yaml`,
  - учитывает `tenant_mode` consumer'а (`required|nullable_transition`) для переходного допуска `tenant_id=null` у non-pools записей,
  - валидирует, что каждый consumer имеет `migrated=true`,
  - формирует отчёт `Go/No-Go` с перечнем блокирующих consumers.
- Без статуса `Go` удаление runtime не выполняется.

## Migration Plan
1. Добавить поля `pool_run.workflow_execution_id`, `workflow_execution.tenant_id`, `workflow_execution.execution_consumer` и runtime metadata `publication_step_state`.
2. Добавить таблицы Variant A: `pool_run_command_log` (idempotency + response snapshot + CAS outcome) и `pool_run_command_outbox` (enqueue/cancel intents).
3. Добавить outbox-dispatcher с at-least-once delivery, retry/backoff и идемпотентной публикацией в `commands:worker:workflows`.
4. Добавить serializer/openapi контракт для status_reason, provenance lineage и команд confirm/abort (включая `Idempotency-Key`).
5. Добавить status projection service с canonical mapping, где primary inputs = `approval_state`, `approved_at`, `publication_step_state`.
6. Включить dual-write: create/start path записывает и facade (`pool_run`) и unified runtime linkage (`workflow_execution`) в одной транзакции с command/outbox артефактами там, где применимо.
7. Включить dual-read для historical/legacy runs и нормализацию legacy provenance (`legacy_reference`, nullable workflow поля).
8. Перевести confirm/abort/retry path на workflow runtime и включить command dedupe storage для `Idempotency-Key` на базе `pool_run_command_log`.
9. Выполнить backfill `pool_run -> workflow_run` и tenant linkage для `execution_consumer=pools`.
10. Включить fail-closed tenant confidentiality (`404 RUN_NOT_FOUND` для cross-tenant/unknown run).
11. Нормализовать foundation template metadata (`workflow_binding`) как compiler hint без изменения публичного API surface.
12. Зафиксировать rollback criteria/runbook: откат routing на legacy path при нарушении SLO, tenant boundary incident или рассинхроне проекции; dual-write остаётся включён до завершения расследования.
13. После стабилизации выключить legacy pool-local execution path.
14. Вести переход по deprecation-plan `legacy-execution-deprecation-plan.md` (фазы, go/no-go, rollback triggers) без немедленного удаления `workflows`.

## Risks / Trade-offs
- Риск: усложнение facade API из-за approval команд.
  - Mitigation: сохранить backward compatibility create/read/retry и добавить минимальные команды confirm/abort.
- Риск: регрессия tenant-изоляции при mixed (legacy + unified) чтении.
  - Mitigation: жёсткая tenant-проверка в facade + миграционные инвариантные тесты.
- Риск: неодинаковая интерпретация retry interval.
  - Mitigation: единый runtime validator (`effective_interval <= 120`) + контрактные тесты.
- Риск: drift между change-ами.
  - Mitigation: зафиксированный source-of-truth rule и cross-reference в proposal/spec/tasks.
- Риск: lag/застревание outbox-dispatcher может задержать enqueue publication/cancel.
  - Mitigation: мониторинг outbox-lag, алерты по stale pending, ручной replay-runbook и idempotent republish.
