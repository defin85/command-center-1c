# Distribution Domain Hard Reset

Внутренняя команда `reset_distribution_domain` очищает distribution-домен одного tenant до clean-slate состояния.

## Что удаляется

- `OrganizationPool`, topology (`PoolNodeVersion`, `PoolEdgeVersion`)
- `PoolWorkflowBinding`
- `PoolRun` и связанный lineage (`PoolRunAuditEvent`, `PoolRunCommandLog`, `PoolRuntimeStepIdempotencyLog`, `PoolRunCommandOutbox`, `PoolPublicationAttempt`)
- `BindingProfile` и `BindingProfileRevision`
- tenant-linked `PoolSchemaTemplate`
- linked distribution runtime tail: `WorkflowExecution`, `WorkflowStepResult`, `WorkflowEnqueueOutbox`, root `BatchOperation`, `Task`
- tenant-linked analyst-facing `WorkflowTemplate` и `DecisionTable`, если они не используются вне target tenant distribution lineage

## Что сохраняется

- `Organizations`
- master-data hub/sync контур: parties, checkpoints, outbox, conflicts, jobs
- system-managed workflow template `Pools Master Data Sync Workflow` и его runtime artifacts
- database metadata / OData cache контур

## Запуск

Dry-run без мутаций:

```bash
cd orchestrator && ./venv/bin/python manage.py reset_distribution_domain --tenant-id <tenant-uuid> --dry-run --json
```

Destructive apply после проверки отчёта:

```bash
cd orchestrator && ./venv/bin/python manage.py reset_distribution_domain --tenant-id <tenant-uuid> --apply --json
```

## Ожидаемый summary

Команда возвращает machine-readable payload:

- `schema_version`
- `execution_mode`: `dry_run` или `apply`
- `overall_status`: `dry_run`, `blocked`, `applied`
- `candidate_counts`
- `preserved_counts`
- `deleted_counts`
- `blockers`

## Fail-Closed blockers

`apply` не начинает destructive cleanup, если preflight находит хотя бы один blocker:

- non-terminal `PoolRun`
- pending `PoolRunCommandOutbox`
- non-terminal linked `WorkflowExecution`
- pending linked `WorkflowEnqueueOutbox`
- shared global `WorkflowTemplate`
- shared global `DecisionTable`

## Важные ограничения

- Cleanup runtime tail вычисляется только по distribution lineage (`PoolRun.workflow_execution_id` и fallback `WorkflowExecution.input_context.pool_run_id`), а не по широкому `execution_consumer="pools"`.
- `WorkflowTemplate` и `DecisionTable` в текущей модели глобальные, а не tenant-scoped. Поэтому команда удаляет только те rows, которые можно безопасно привязать к target tenant distribution lineage.
- Если global workflow/decision используется вне target tenant, команда завершится `blocked` до любых мутаций.
- Повторный `--apply` на уже очищенном tenant допустим: команда должна вернуть zero-delta summary.
