# Release Notes — 2026-03-10

## refactor-14-workflow-centric-hardening

### Что изменилось

- /decisions становится primary surface для workflow-centric `document_policy` authoring, revise/import и metadata-aware preview.
- `workflow executor templates remain available here only as a compatibility/integration path`: `/templates` остаётся catalog atomic operations и больше не должен трактоваться как primary analyst-facing workflow modeling surface.
- Legacy edge document_policy editor в `/pools/catalog` переведён в compatibility mode:
  - existing payload показывается read-only по умолчанию;
  - import идёт через явное действие в `/decisions`;
  - deterministic API path: `POST /api/v2/pools/{pool_id}/document-policy-migrations/`.
- Для avoid-regression parity: legacy edge document_policy editor больше не считается primary net-new authoring path.
- Decision authoring/import и migration path теперь опираются на shared configuration-scoped metadata snapshots:
  - в UI/API видны `snapshot_id`, `resolution_mode`, `metadata_hash`, `is_shared_snapshot`, `provenance_database_id`;
  - одинаковый `config_version` сам по себе больше не считается достаточным условием reuse.
- `/workflows` закреплён как composition surface, а `/pools/runs` как operator lifecycle/read-model surface для create/inspect/confirm/retry.

### Operator actions before tenant cutover

1. Прогнать canonical binding backfill:
   - `cd orchestrator && ./venv/bin/python manage.py backfill_pool_workflow_bindings --dry-run --json`
2. Прогреть shared metadata snapshots на representative infobase каждой configuration profile:
   - `POST /api/v2/pools/odata-metadata/catalog/refresh/`
3. Для pool-ов с legacy edge policies выполнить import в `/decisions`:
   - UI: `/pools/catalog` -> `Import to /decisions`
   - API: `POST /api/v2/pools/{pool_id}/document-policy-migrations/`
4. Только после этого включать tenant-scoped rollout marker `workflows.authoring.phase=workflow_centric_active`.

### Breaking / migration notes

- Legacy edge document_policy editor больше не является рекомендуемым net-new path; canonical route для новых policy revisions теперь `/decisions`.
- External/operator tooling не должно рассчитывать на database-local-only metadata context. Проверяйте `resolution_mode` и `metadata_hash`, а не только `database_id` или `config_version`.
- Если import legacy policy завершился с `binding_update_required=true`, rollout нельзя считать завершённым, пока binding refs не закреплены явно.
- Explicit `pool_workflow_binding_id` requirement для preview/create-run остаётся обязательным; подробности см. в [2026-02-15-pools-run-input-breaking-change.md](./2026-02-15-pools-run-input-breaking-change.md).

### Rollback window

- Rollback window держится открытым до завершения pilot tenant и первого scale-out batch.
- В течение этого окна не удаляйте:
  - last-known-good inactive binding revisions;
  - legacy edge metadata, если import evidence ещё не зафиксирован;
  - cutover evidence по `snapshot_id` / `Decision ref` / `Updated bindings`.
- Rollback делается tenant-scoped через marker/binding switchback, а не через переписывание historical runs.

### Canonical references

- Runbook: [WORKFLOW_CENTRIC_POOLS_RUNBOOK.md](../observability/WORKFLOW_CENTRIC_POOLS_RUNBOOK.md)
- Cutover notes: [refactor-14-workflow-centric-hardening/cutover.md](/home/egor/code/command-center-1c/openspec/changes/refactor-14-workflow-centric-hardening/cutover.md)
