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
- `status_reason`: подстатус facade-модели только для `validated` (`preparing`, `awaiting_approval`, `queued`); для остальных статусов `null`.

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
- Decision: canonical status mapping фиксируется и обязателен для API:
  - `draft` — run создан, workflow run ещё не создан;
  - `validated` + `status_reason=preparing` — `workflow.status in {pending, running}`, `approval_required=true`, `approved_at is null`, `approval_state=preparing`;
  - `validated` + `status_reason=awaiting_approval` — `workflow.status=pending`, `approval_required=true`, `approved_at is null`, `approval_state=awaiting_approval`;
  - `validated` + `status_reason=queued` — `workflow.status=pending`, `approval_required=false` или `approved_at is not null`;
  - `publishing` — `workflow.status=running`, `approval_required=false` или `approved_at is not null`;
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
  - `confirm-publication` идемпотентен в состояниях после подтверждения и не создаёт duplicate enqueue;
  - `abort-publication` допустим только до старта шага `publication_odata`;
  - после старта `publication_odata` команда `abort-publication` возвращает business conflict.
- Decision: для historical/legacy runs без workflow-link возвращается совместимый provenance:
  - `workflow_run_id=null`,
  - `workflow_status=null`,
  - `execution_backend=legacy_pool_runtime`,
  - `retry_chain=[]`,
  - `legacy_reference` при наличии.
- Decision: удаление `workflows` запрещено до preflight-проверки consumer registry:
  - owner: platform team;
  - source-of-truth: `execution_consumers_registry` с флагами миграции;
  - decommission разрешён только когда все consumers помечены `migrated=true`.

## Architecture Invariants (Anti-Drift)
- Invariant 1: `workflows` остаётся единственным runtime для `pools`; второй lifecycle в `intercompany_pools` запрещён.
- Invariant 2: при `approval_required=true` и `approved_at is null` facade НЕ может возвращать `pool:publishing`.
- Invariant 3: `safe` run проходит фазы `approval_state=preparing -> awaiting_approval -> approved`; `unsafe` использует `approval_state=not_required`.
- Invariant 4: `status_reason` разрешён только для `pool:validated` и ограничен `preparing|awaiting_approval|queued`.
- Invariant 5: `abort-publication` после старта шага `publication_odata` всегда возвращает business conflict.
- Invariant 6: runtime endpoint retry фиксирован как `POST /api/v2/pools/runs/{run_id}/retry`.
- Invariant 7: `PoolImportSchemaTemplate` трактуется как execution-core алиас foundation `PoolSchemaTemplate`, без нового публичного артефакта.
- Invariant 8: при конфликте формулировок runtime приоритет имеет `pool-workflow-execution-core/spec.md`; foundation change используется только как domain vocabulary.

## Change Synchronization Rule
- Любая правка runtime-семантики в этом change ДОЛЖНА обновлять в одном коммите:
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/proposal.md`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/design.md`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/tasks.md`
  - `openspec/changes/refactor-unify-pools-workflow-execution-core/specs/pool-workflow-execution-core/spec.md`

## Status Projection Contract
- `draft`: pool run существует, workflow run ещё не создан.
- `validated/preparing`: pre-publish шаги ещё выполняются или ставятся в очередь до точки ручного решения.
- `validated/awaiting_approval`: workflow run создан, ожидает явного решения пользователя.
- `validated/queued`: workflow run готов к исполнению и находится в очереди.
- `publishing`: workflow исполняется в фазе публикации/дозаписи после автоматического или ручного подтверждения.
- `published`: завершено без failed targets.
- `partial_success`: завершено с failed targets.
- `failed`: workflow завершился `failed` или `cancelled` (включая `abort-publication`).
- `status_reason`: применяется только для `validated`; допустимые значения `preparing|awaiting_approval|queued`.
- Для остальных facade-статусов `status_reason` возвращается `null`.

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
  - переводит `safe` run из `awaiting_approval` в `queued`/`publishing`;
  - повторный вызов идемпотентен и не создаёт duplicate enqueue.
- `POST /api/v2/pools/runs/{run_id}/abort-publication`:
  - завершает run как `failed` через workflow `cancelled`, если `publication_odata` ещё не начат;
  - повторный вызов идемпотентен, если run уже отменён этим же действием.
- Для terminal run (`published|partial_success|failed`) команды confirm/abort возвращают business conflict без изменения состояния.
- Для run, где уже начат `publication_odata`, `abort-publication` возвращает business conflict без изменения состояния.

## Decommission Preflight Contract
- Перед любым `workflows` decommission запускается preflight:
  - читает `execution_consumers_registry`,
  - валидирует, что каждый consumer имеет `migrated=true`,
  - формирует отчёт `Go/No-Go` с перечнем блокирующих consumers.
- Без статуса `Go` удаление runtime не выполняется.

## Migration Plan
1. Добавить поля `pool_run.workflow_execution_id`, `workflow_execution.tenant_id`, `workflow_execution.execution_consumer`.
2. Добавить serializer/openapi контракт для status_reason, provenance lineage и команд confirm/abort.
3. Добавить status projection service с canonical mapping, reason-кодами и `approval_state`.
4. Перевести create/start path `pools/runs` на workflow runtime с `safe/unsafe` approval gate и pre-publish шагами до ручного решения.
5. Добавить confirm/abort команды фасада для safe-mode.
6. Перевести retry path на failed-subset re-execution через workflow runtime.
7. Включить dual-read для historical/legacy runs и нормализацию legacy provenance (`legacy_reference`, nullable workflow поля).
8. Выполнить backfill `pool_run -> workflow_run` и tenant linkage для `execution_consumer=pools`.
9. Нормализовать foundation template metadata (`workflow_binding`) как compiler hint без изменения публичного API surface.
10. После стабилизации выключить legacy pool-local execution path.

## Risks / Trade-offs
- Риск: усложнение facade API из-за approval команд.
  - Mitigation: сохранить backward compatibility create/read/retry и добавить минимальные команды confirm/abort.
- Риск: регрессия tenant-изоляции при mixed (legacy + unified) чтении.
  - Mitigation: жёсткая tenant-проверка в facade + миграционные инвариантные тесты.
- Риск: неодинаковая интерпретация retry interval.
  - Mitigation: единый runtime validator (`effective_interval <= 120`) + контрактные тесты.
- Риск: drift между change-ами.
  - Mitigation: зафиксированный source-of-truth rule и cross-reference в proposal/spec/tasks.
