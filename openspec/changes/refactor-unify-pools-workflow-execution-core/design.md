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
- `PoolImportSchemaTemplate`: публичный XLSX/JSON шаблон импорта (domain-level).
- `PoolExecutionPlan`: скомпилированный workflow-compatible graph для конкретного run-контекста.
- `status_reason`: подстатус facade-модели (`awaiting_approval`, `queued`, `running`, `completed`, `failed`).

## Decisions
- Decision: `workflows` является execution-core для `pools`.
- Decision: source-of-truth для runtime-семантики `pools/runs*` задаётся этим change; `add-intercompany-pool-distribution-module` остаётся source-of-truth для foundation/domain vocabulary.
- Decision: терминология разделяется:
  - `PoolImportSchemaTemplate` не тождественен `WorkflowTemplate`;
  - compiler создаёт `PoolExecutionPlan` детерминированно из `pool_id + period + direction + source_hash + template_version`.
- Decision: `safe/unsafe` реализуются внутри workflow runtime, без второго оркестратора:
  - `safe`: workflow run создаётся в `pending` с `approval_required=true`, публикационные шаги не enqueue до явного подтверждения;
  - `unsafe`: `approved_at` проставляется автоматически на create/start path;
  - явные команды фасада: `confirm-publication` и `abort-publication`.
- Decision: canonical status mapping фиксируется и обязателен для API:
  - `draft` — run создан, workflow run ещё не создан;
  - `validated` + `status_reason=awaiting_approval` — `workflow.status=pending`, `approval_required=true`, `approved_at is null`;
  - `validated` + `status_reason=queued` — `workflow.status=pending`, `approval_required=false` или `approved_at is not null`;
  - `publishing` — `workflow.status=running`;
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
  - `max_attempts_total=5` (включая initial attempt);
  - `retry_interval_seconds` конфигурируем (`run override > template default > system default`);
  - эффективный интервал ограничен 120 секундами.
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

## Status Projection Contract
- `draft`: pool run существует, workflow run ещё не создан.
- `validated/awaiting_approval`: workflow run создан, ожидает явного решения пользователя.
- `validated/queued`: workflow run готов к исполнению и находится в очереди.
- `publishing`: workflow step execution активен.
- `published`: завершено без failed targets.
- `partial_success`: завершено с failed targets.
- `failed`: workflow завершился `failed` или `cancelled` (включая `abort-publication`).

## Execution Mapping (Target)
- `PoolImportSchemaTemplate` + run context -> compiler -> `PoolExecutionPlan` -> `WorkflowTemplate`.
- `PoolRun(start)`:
  - `unsafe`: create workflow run + auto-approval + enqueue;
  - `safe`: create workflow run (`approval_required=true`) без publication enqueue до confirm command.
- Workflow steps:
  - `prepare_input` (source/template validation),
  - `approval_gate` (safe only; resume by `confirm-publication`),
  - `distribution_calculation` (top-down/bottom-up),
  - `publication_odata` (document upsert + posting),
  - `reconciliation_report` (balance checks + artifacts).

## Provenance Contract (API)
- Базовые поля (всегда присутствуют в payload):
  - `workflow_run_id` (nullable),
  - `workflow_status` (nullable),
  - `execution_backend` (`workflow_core` | `legacy_pool_runtime`),
  - `retry_chain` (array, может быть пустым).
- Для unified execution дополнительно обязательны:
  - `publication_identity_strategy`,
  - `publication_external_document_id`,
  - `publication_attempts[]` с каноническими diagnostic fields.

## Decommission Preflight Contract
- Перед любым `workflows` decommission запускается preflight:
  - читает `execution_consumers_registry`,
  - валидирует, что каждый consumer имеет `migrated=true`,
  - формирует отчёт `Go/No-Go` с перечнем блокирующих consumers.
- Без статуса `Go` удаление runtime не выполняется.

## Migration Plan
1. Добавить поля `pool_run.workflow_execution_id`, `workflow_execution.tenant_id`, `workflow_execution.execution_consumer`.
2. Добавить serializer/openapi контракт для status_reason и provenance nullable-правил.
3. Добавить status projection service с canonical mapping и reason-кодами.
4. Перевести create/start path `pools/runs` на workflow runtime с `safe/unsafe` approval gate.
5. Добавить confirm/abort команды фасада для safe-mode.
6. Перевести retry path на failed-subset re-execution через workflow runtime.
7. Включить dual-read для historical/legacy runs и нормализацию legacy provenance.
8. Выполнить backfill `pool_run -> workflow_run` и tenant linkage для `execution_consumer=pools`.
9. После стабилизации выключить legacy pool-local execution path.

## Risks / Trade-offs
- Риск: усложнение facade API из-за approval команд.
  - Mitigation: сохранить backward compatibility create/read/retry и добавить минимальные команды confirm/abort.
- Риск: регрессия tenant-изоляции при mixed (legacy + unified) чтении.
  - Mitigation: жёсткая tenant-проверка в facade + миграционные инвариантные тесты.
- Риск: неодинаковая интерпретация retry interval.
  - Mitigation: единый runtime validator (`effective_interval <= 120`) + контрактные тесты.
- Риск: drift между change-ами.
  - Mitigation: зафиксированный source-of-truth rule и cross-reference в proposal/spec/tasks.
