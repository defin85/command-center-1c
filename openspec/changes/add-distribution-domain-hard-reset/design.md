## Контекст
Distribution-домен уже хранит данные не только в `OrganizationPool` и topology. На runtime path он создаёт `PoolRun`, audit/outbox/log rows, `WorkflowExecution`, `WorkflowStepResult`, workflow enqueue outbox и root `BatchOperation` projection. Reusable authoring catalog вынесен в `binding_profiles`, `decisions` и `workflows`, а import/run path использует `schema_templates`.

При этом часть соседнего master-data контура живёт в тех же Django app и моделях. Особенно важны два пересечения:
- `WorkflowExecution.execution_consumer="pools"` используется как distribution run, так и master-data sync.
- master-data sync использует system-managed `WorkflowTemplate`, который нельзя терять, если master-data должен остаться рабочим.

Поэтому hard reset нельзя строить как "удалить всё, где consumer = pools" или "удалить вообще все workflow templates".

## Цели
- Дать оператору воспроизводимый tenant-scoped hard reset distribution-домена.
- Снести analyst-facing distribution artifacts и их runtime tail до состояния "можно начать моделирование с нуля".
- Сохранить `Organizations` и весь master-data контур.
- Сделать reset fail-closed, без частичного запуска на активных процессах.
- Обеспечить повторяемость: dry-run до apply, идемпотентный повторный apply после частичной очистки/сбоя.

## Не-цели
- Не вводить публичный HTTP API или UI для destructive reset.
- Не удалять `Organizations`.
- Не удалять master-data hub/sync/bootstrap/checkpoint/outbox/conflict artifacts.
- Не удалять database metadata / OData catalog caches.
- Не удалять system-managed master-data workflow template.
- Не делать broad cross-tenant reset.
- Не поддерживать override/force bypass для активных run/execution в рамках этого change.

## Решения

### Decision 1: Reset оформляется как internal management command, а не как HTTP endpoint
Операция destructive и редкая. Ей нужен explicit operator intent, а не обычный продуктовый UX-path. Поэтому canonical entry point:
- internal Django management command;
- explicit tenant selector;
- отдельные режимы `--dry-run` и `--apply`.

`dry-run` показывает candidate counts и blockers. `apply` допустим только после успешного preflight.

### Decision 2: Change фиксирует один reset profile `full_distribution_reset`
Вместо набора loosely-coupled флагов change вводит один явный профиль:
- `pools` + topology;
- `pool_workflow_bindings`;
- `pool_runs` и их lineage/outbox/audit/publication attempts;
- `binding_profiles` + `binding_profile_revisions`;
- analyst-facing `decisions`;
- analyst-facing `workflows`;
- `schema_templates`;
- linked workflow/operations tail.

Это делает destructive scope читаемым и снижает риск полуочищенного состояния.

### Decision 3: Preserve-scope фиксируется явно
Reset НЕ ДОЛЖЕН затрагивать:
- `Organizations`;
- `pool master-data` entities, sync jobs, checkpoints, outbox, conflicts, bootstrap artifacts;
- database metadata / OData catalog caches;
- system-managed master-data workflow template `Pools Master Data Sync Workflow` и его runtime artifacts.

Если в будущем потребуется отдельный master-data reset, это будет другой change с отдельным contract.

### Decision 4: Workflow/operations cleanup вычисляется по distribution lineage, а не по broad consumer label
`execution_consumer="pools"` недостаточен для purge scope, потому что его используют и `pool_runs`, и master-data sync jobs.

Поэтому purge-candidate execution set строится только из distribution lineage:
- `PoolRun.workflow_execution_id`;
- совместимый fallback: `WorkflowExecution.input_context.pool_run_id`, если execution ещё не связан в row полем;
- связанный `BatchOperation.id == workflow_execution_id`;
- `WorkflowEnqueueOutbox.operation_id == workflow_execution_id`;
- `Task.batch_operation_id` для соответствующих root operations.

Это гарантирует, что reset не заденет master-data sync jobs/executions, даже если они используют тот же consumer label.

### Decision 5: Analyst-facing workflow purge исключает preserved system-managed template
Пользователь хочет снести `workflows` из distribution authoring catalog, но сохранить master-data. В текущем коде master-data sync relies on system-managed template `Pools Master Data Sync Workflow`, который автоматически поддерживается helper-ом `ensure_pool_master_data_sync_workflow_template()`.

Поэтому purge workflow catalog трактуется как удаление analyst-facing distribution workflows и их obsolete runtime lineage, но с explicit exclusion для preserved system-managed master-data template.

### Decision 6: Cleanup выполняется ordered phase-by-phase и должен быть rerunnable
Одна гигантская транзакция на весь tenant reset рискованна из-за объёма и cross-app delete fan-out. Вместо этого command работает фазами, каждая внутри `transaction.atomic()`, а общий preflight выполняется до первого destructive шага.

Базовый порядок фаз:
1. собрать purge candidate ids и выполнить preflight;
2. удалить `PoolRunCommandOutbox`, `PoolRuntimeStepIdempotencyLog`, `PoolRunCommandLog`, `PoolRunAuditEvent`, `PoolPublicationAttempt`;
3. удалить `WorkflowEnqueueOutbox`, `Task`, root `BatchOperation`, `WorkflowStepResult`, `WorkflowExecution` для distribution candidate set;
4. удалить `PoolRun`;
5. удалить `PoolWorkflowBinding`;
6. удалить `PoolEdgeVersion` и `PoolNodeVersion`;
7. удалить `OrganizationPool`;
8. удалить `BindingProfileRevision` и `BindingProfile`;
9. удалить analyst-facing `DecisionTable`;
10. удалить analyst-facing `WorkflowTemplate`, кроме preserved master-data template;
11. удалить `PoolSchemaTemplate`.

Если выполнение падает между фазами, повторный запуск ДОЛЖЕН безопасно довести состояние до целевого empty-state.

### Decision 7: Preflight остаётся fail-closed
Команда обязана остановиться до мутаций, если обнаружены blockers:
- non-terminal `PoolRun`;
- pending `PoolRunCommandOutbox`;
- non-terminal linked `WorkflowExecution`;
- pending linked `WorkflowEnqueueOutbox`;
- иные linked rows, которые означают, что distribution workflow ещё исполняется.

Оператор сначала завершает/останавливает активные процессы, затем запускает reset повторно.

## Альтернативы

### Alternative A: Удалять всё с `execution_consumer="pools"`
Отклонено:
- сломает master-data sync;
- нарушает явное пользовательское требование сохранить master-data.

### Alternative B: Ограничиться deactivate/archive для reusable artifacts
Отклонено:
- не даёт "чистого листа";
- сохраняет legacy зависимости в `binding_profiles` / `decisions` / `workflows`.

### Alternative C: Делать hard reset через публичный API/UI
Отклонено:
- слишком высокий риск accidental destructive trigger;
- хуже auditability и operator discipline по сравнению с internal command.

## Риски и компромиссы
- Analyst-facing и system-managed workflow templates живут в одной модели; purge contract обязан явно различать их.
- Если в tenant остались legacy executions без `PoolRun.workflow_execution_id`, cleanup придётся опираться на `input_context.pool_run_id`.
- Phase-by-phase apply не гарантирует one-shot global rollback, поэтому идемпотентность и точный phase summary обязательны.
- Слишком широкий candidate query может задеть master-data, слишком узкий может оставить orphan rows; поэтому tests на preserved master-data boundary обязательны.

## План миграции
1. Зафиксировать spec нового reset capability.
2. Реализовать preflight и summary-only `dry-run`.
3. Реализовать lineage-based delete phases для distribution runtime tail.
4. Реализовать purge reusable authoring catalog с explicit preserved exclusions.
5. Добавить regression tests на boundaries master-data vs distribution.

## Открытые вопросы
- Нужен ли после этого отдельный follow-up change для selective reset profile без reusable catalog purge, или текущего `full_distribution_reset` достаточно?
