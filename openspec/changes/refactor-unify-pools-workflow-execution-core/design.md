## Context
Целевой поток для pools должен использовать уже существующий execution stack (`workflows` + worker queue + audit/provenance), а не развивать второй runtime в `intercompany_pools`.

Сейчас в коде есть расхождения:
- разные статусные модели (`pool_runs.status` и `workflow_executions.status`);
- tenant-scoped `PoolRun` против workflow-моделей без tenant reference;
- разные уровни retry (`max_attempts=5` в pools и workflow-level/node-level настройки);
- нефиксированный queueing/SLA контракт.

Этот change закрывает именно эти расхождения и принимает execution-scope, вынесенный из `add-intercompany-pool-distribution-module`.

## Goals / Non-Goals
- Goals:
  - Один runtime исполнения для pools через `templates/workflow`.
  - Детерминированная status projection без open questions.
  - Явная tenant-изоляция `pool_run <-> workflow_run`.
  - Единый retry и provenance контракт для API/UI.
- Non-Goals:
  - Big-bang удаление `workflows`.
  - Перепроектирование доменной математики top-down/bottom-up.
  - Введение отдельной queue-инфраструктуры для pools в phase 1.

## Decisions
- Decision: `workflows` является execution-core для `pools`.
- Decision: `Pool Schema Template` компилируется в workflow-compatible graph (operation nodes + I/O mapping + retry policy).
- Decision: `pools/runs*` остаётся доменным API-слоем и хранит reference на workflow run + provenance block.
- Decision: publication service (OData) исполняется только как adapter шага в workflow graph.
- Decision: canonical status mapping фиксируется и обязателен для API:
  - `draft` — run создан, workflow run ещё не создан;
  - `validated` — `workflow.status=pending`;
  - `publishing` — `workflow.status=running`;
  - `published` — `workflow.status=completed` и `failed_targets=0`;
  - `partial_success` — `workflow.status=completed` и `failed_targets>0`;
  - `failed` — `workflow.status in {failed, cancelled}`.
- Decision: tenant boundary обязателен:
  - `WorkflowExecution` получает tenant reference;
  - `pool_run.tenant_id == workflow_execution.tenant_id` проверяется на create/read/retry path.
- Decision: идемпотентность `pool` домена сохраняется и прокидывается в workflow metadata/idempotency.
- Decision: retry-контракт фиксированный:
  - domain contract: `max_attempts_total=5` для publication;
  - compiler/runtime mapping: initial attempt + bounded retries на уровне publication step;
  - `/pools/runs/{id}/retry` повторяет только failed subset через workflow runtime.
- Decision: queueing phase 1 фиксируется:
  - stream: `commands:worker:workflows`;
  - execution priority: `normal` по умолчанию;
  - dedicated SLA lane отложен (вне scope этого change).
- Decision: удаление `workflows` запрещено до завершения миграции всех runtime consumers.
- Decision: foundation задачи (catalog/data/contracts/UI baseline) не дублируются в этом change и считаются входом из `add-intercompany-pool-distribution-module`.

## Execution Mapping (Target)
- `PoolTemplate` -> compiler -> `WorkflowTemplate`.
- `PoolRun(start)` -> create/start `WorkflowExecution`.
- Workflow steps:
  - `prepare_input` (source/template validation),
  - `distribution_calculation` (top-down/bottom-up),
  - `publication_odata` (document upsert + posting),
  - `reconciliation_report` (balance checks + artifacts).
- API pools возвращает:
  - pool-доменные поля,
  - `workflow_run_id`,
  - `workflow_status`,
  - `provenance` (backend/step diagnostics/retry chain).

## Migration Plan
1. Добавить tenant/reference поля и provenance-block контракт:
  - `pool_run.workflow_execution_id` (nullable),
  - tenant reference в workflow execution,
  - serializer/openapi обновления.
2. Добавить status projection service с каноническим mapping.
3. Перевести create/start path `pools/runs` на workflow runtime.
4. Перевести retry path на failed-subset re-execution через workflow runtime.
5. Включить dual-read для historical/legacy run записей.
6. Выполнить backfill `pool_run -> workflow_run` и tenant linkage.
7. После стабилизации выключить legacy pool-local execution path.

## Risks / Trade-offs
- Риск: рассинхронизация доменных и runtime статусов.
  - Mitigation: единый mapping service + контрактные API тесты.
- Риск: регрессия tenant-изоляции при legacy/historical чтении.
  - Mitigation: жёсткая tenant-проверка в facade + миграционные инвариантные тесты.
- Риск: изменение retry-поведения для частично успешных run.
  - Mitigation: интеграционные тесты `partial_success -> retry_failed_subset`.
- Риск: рост задержек в общей workflow очереди.
  - Mitigation: telemetry по stream depth/latency и отдельный follow-up change при необходимости dedicated lane.
