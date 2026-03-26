# Change: add-distribution-domain-hard-reset

## Почему
- Для distribution-домена нужен воспроизводимый "чистый лист": сейчас в системе есть только lifecycle `deactivate`/`is_active`, но нет tenant-scoped purge для `pool` и связанных distribution-артефактов.
- Простое удаление текущих записей небезопасно: модель содержит cross-app зависимости и `PROTECT`/lineage связи между `pool_runs`, `pool_workflow_bindings`, `binding_profiles`, `workflow_executions`, `workflow_enqueue_outbox` и root `batch_operations`.
- В reusable authoring catalog (`binding_profiles`, analyst-facing `decisions`, analyst-facing `workflows`) остались legacy зависимости, которые мешают начать моделирование распределения с нуля.
- При этом пользователь явно хочет сохранить `Organizations` и весь master-data контур, включая его sync/bootstrapping/runtime артефакты.

## Что меняется
- Вводится внутренняя capability `distribution-domain-reset`: tenant-scoped destructive reset для distribution-домена без публичного HTTP API.
- Change фиксирует один operator-confirmed профиль reset: `full_distribution_reset`.
- `full_distribution_reset` удаляет:
  - `pools`, их topology, workflow bindings и runs;
  - lineage и outbox, связанные с `pool_runs`;
  - `binding_profiles` и их revisions;
  - analyst-facing `decisions`;
  - analyst-facing `workflows`, кроме system-managed workflow template, необходимого для сохранённого master-data контура;
  - `schema_templates`, используемые distribution run/import flow.
- Reset выполняется только через explicit `dry-run` / `apply` flow и fail-closed preflight.
- Reset сохраняет:
  - `Organizations`;
  - master-data hub/sync/bootstrap/conflict/outbox/checkpoint artifacts;
  - database metadata / OData catalog caches;
  - system-managed master-data workflow template и связанные с ним sync jobs/executions.

## Impact
- Affected specs:
  - `distribution-domain-reset` (new)
- Affected code:
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/operations/**`
  - management commands + backend tests
