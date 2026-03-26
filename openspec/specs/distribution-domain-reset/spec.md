# distribution-domain-reset Specification

## Purpose
TBD - created by archiving change add-distribution-domain-hard-reset. Update Purpose after archive.
## Requirements
### Requirement: Distribution domain hard reset MUST provide a tenant-scoped clean-slate profile
Система ДОЛЖНА (SHALL) предоставлять внутреннюю capability `distribution-domain-reset` для tenant-scoped destructive reset distribution-домена.

В рамках этого change система ДОЛЖНА (SHALL) поддерживать профиль `full_distribution_reset`, который удаляет:
- `OrganizationPool`, `PoolNodeVersion`, `PoolEdgeVersion`;
- `PoolWorkflowBinding`;
- `PoolRun`, `PoolRunAuditEvent`, `PoolRunCommandLog`, `PoolRuntimeStepIdempotencyLog`, `PoolRunCommandOutbox`, `PoolPublicationAttempt`;
- `BindingProfile` и `BindingProfileRevision`;
- analyst-facing `DecisionTable`;
- analyst-facing `WorkflowTemplate`;
- `PoolSchemaTemplate`;
- runtime/operations хвост, связанный с удаляемыми distribution run/execution rows.

Система ДОЛЖНА (SHALL) сохранять:
- `Organizations`;
- master-data hub/sync/bootstrap/checkpoint/outbox/conflict artifacts;
- database metadata / OData catalog caches;
- system-managed master-data workflow template и его runtime artifacts.

#### Scenario: Full distribution reset очищает distribution artifacts и сохраняет preserved shared domain
- **GIVEN** в tenant существуют `pools`, bindings, runs, reusable binding profiles, analyst-facing decisions/workflows и schema templates
- **AND** в том же tenant существуют `Organizations` и master-data sync artifacts
- **WHEN** оператор запускает `full_distribution_reset`
- **THEN** distribution artifacts удаляются до empty-state
- **AND** `Organizations` остаются нетронутыми
- **AND** master-data artifacts остаются нетронутыми

### Requirement: Hard reset MUST be explicit, preflighted, and fail-closed
Система ДОЛЖНА (SHALL) выполнять hard reset только через internal operator path с explicit tenant selector и отдельными режимами `dry-run` и `apply`.

`dry-run` ДОЛЖЕН (SHALL) возвращать:
- candidate counts по scope reset;
- preserved counts по сохранённым доменам;
- список blocking diagnostics.

`apply` НЕ ДОЛЖЕН (SHALL NOT) начинать destructive cleanup, если preflight обнаружил blockers.

Blockers ДОЛЖНЫ (SHALL) включать как минимум:
- non-terminal `PoolRun`;
- pending `PoolRunCommandOutbox`;
- non-terminal linked `WorkflowExecution`;
- pending linked `WorkflowEnqueueOutbox`.

#### Scenario: Active run блокирует destructive reset до мутаций
- **GIVEN** tenant содержит `PoolRun` в non-terminal состоянии
- **WHEN** оператор запускает hard reset в режиме `apply`
- **THEN** команда завершается fail-closed без destructive мутаций
- **AND** оператор получает machine-readable blocker summary

#### Scenario: Dry-run показывает scope reset без побочных эффектов
- **GIVEN** tenant содержит distribution artifacts и preserved shared artifacts
- **WHEN** оператор запускает hard reset в режиме `dry-run`
- **THEN** команда возвращает counts и diagnostics
- **AND** ни одна запись в БД не удаляется

### Requirement: Runtime cleanup MUST be derived from distribution lineage, not broad consumer labels
Система ДОЛЖНА (SHALL) определять purge-candidate `workflow_executions`, `workflow_step_results`, `workflow_enqueue_outbox`, root `batch_operations` и related `tasks` только из distribution lineage.

В рамках этого change authoritative candidate sources ДОЛЖНЫ (SHALL) включать:
- `PoolRun.workflow_execution_id`;
- совместимый fallback через `WorkflowExecution.input_context.pool_run_id`.

Система НЕ ДОЛЖНА (SHALL NOT) использовать `execution_consumer="pools"` как единственный критерий purge scope.

#### Scenario: Master-data execution с тем же consumer label не попадает в purge scope
- **GIVEN** tenant содержит distribution `WorkflowExecution`, связанный с `pool_run_id`
- **AND** tenant содержит master-data sync `WorkflowExecution` с тем же `execution_consumer="pools"`, но без связи с `pool_run_id`
- **WHEN** оператор запускает `full_distribution_reset`
- **THEN** distribution execution и его linked operations tail попадают в purge
- **AND** master-data sync execution и его linked artifacts не удаляются

### Requirement: Workflow purge MUST preserve system-managed master-data template
Система ДОЛЖНА (SHALL) трактовать purge `workflows` в `full_distribution_reset` как очистку analyst-facing distribution workflow catalog, но НЕ ДОЛЖНА (SHALL NOT) удалять system-managed workflow template, необходимый для сохранённого master-data контура.

#### Scenario: System-managed master-data workflow template survives workflow purge
- **GIVEN** tenant содержит analyst-facing workflow templates для distribution authoring
- **AND** tenant содержит system-managed template для pool master-data sync
- **WHEN** оператор запускает `full_distribution_reset`
- **THEN** analyst-facing distribution workflows удаляются
- **AND** system-managed master-data workflow template остаётся доступным

### Requirement: Hard reset apply MUST be ordered and rerunnable
Система ДОЛЖНА (SHALL) выполнять destructive cleanup dependency-safe фазами и обеспечивать safe повторный запуск на уже частично или полностью очищенном tenant state.

Повторный `apply` после успешно завершённого reset ДОЛЖЕН (SHALL) завершаться успешно с zero-or-empty delta summary, а не падать на отсутствии ранее удалённых строк.

#### Scenario: Повторный apply на уже очищенном tenant state остаётся успешным
- **GIVEN** tenant уже очищен предыдущим успешным `full_distribution_reset`
- **WHEN** оператор повторно запускает `apply`
- **THEN** команда завершается успешно
- **AND** summary показывает отсутствие новых кандидатов на удаление

