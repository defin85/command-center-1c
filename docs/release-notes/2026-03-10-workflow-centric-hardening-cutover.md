# Release Notes — 2026-03-10

## refactor-14-workflow-centric-hardening

### Что изменилось

- /decisions становится primary surface для workflow-centric `document_policy` authoring, revise/import и metadata-aware preview.
- `workflow executor templates remain available here only as a compatibility/integration path`: `/templates` остаётся catalog atomic operations и больше не должен трактоваться как primary analyst-facing workflow modeling surface.
- Legacy edge document_policy editor в `/pools/catalog` переведён в compatibility mode:
  - existing payload показывается read-only по умолчанию;
  - import идёт через явное действие в `/decisions`;
  - `Import raw JSON` внутри `/decisions` остаётся explicit compatibility-only fallback;
  - deterministic API path: `POST /api/v2/pools/{pool_id}/document-policy-migrations/`.
- Для avoid-regression parity: legacy edge document_policy editor больше не считается primary net-new authoring path.
- Decision authoring/import и migration path теперь опираются на shared business-identity metadata snapshots:
  - в UI/API видны `config_name`, `config_version`, `config_generation_id`, `metadata_hash`, `observed_metadata_hash`, `publication_drift`, `is_shared_snapshot`, `provenance_database_id`;
  - одинаковая business identity `config_name + config_version` определяет reuse, а `metadata_hash`/`publication_drift` остаются diagnostics-only markers.
- Reusable subworkflow calls закреплены на pinned subworkflow revision: runtime использует `subworkflow_ref(binding_mode="pinned_revision")` и отклоняет drift/mismatch fail-closed вместо silent fallback на latest revision.
- `/workflows` закреплён как composition surface, а `/pools/runs` как operator lifecycle/read-model surface для create/inspect/confirm/retry.

### Operator actions before tenant cutover

1. Прогнать canonical binding backfill:
   - `cd orchestrator && ./venv/bin/python manage.py backfill_pool_workflow_bindings --dry-run --json`
2. Прогнать one-time business identity backfill для legacy snapshot/resolution и historical decision rows:
   - dry-run: `cd orchestrator && ./venv/bin/python manage.py backfill_business_identity_state --dry-run --json`
   - apply-run: `cd orchestrator && ./venv/bin/python manage.py backfill_business_identity_state --json`
   - После этого canonical metadata snapshot / scope resolution больше не делятся по `extensions_fingerprint`; marker сохраняется только для diagnostics/provenance.
3. Прогреть shared metadata snapshots на representative infobase каждой configuration profile:
   - открыть `/databases`
   - выбрать representative database для нужной business identity
   - в `Metadata management` при необходимости запустить `Re-verify configuration identity`, затем `Refresh metadata snapshot`
4. Для pool-ов с legacy edge policies выполнить import в `/decisions`:
   - UI: `/decisions` -> `Import legacy edge`
   - explicit compatibility-only fallback: `/decisions` -> `Import raw JSON`
   - Compatibility UI shortcut: `/pools/catalog` -> `Import to /decisions`
   - API: `POST /api/v2/pools/{pool_id}/document-policy-migrations/`
5. Только после этого включать tenant-scoped rollout marker `workflows.authoring.phase=workflow_centric_active`.
6. Для checked-in proof shipped default path использовать:
   - `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md`
7. Evidence capture во время live tenant cutover вести по checked-in templates:
   - `docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json`
   - `docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json`
   - `docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json`
8. После capture собрать tenant-scoped live bundle по стабильному artifact path:
   - `docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`
   - verifier: `cd orchestrator && ../.venv/bin/python manage.py verify_workflow_hardening_cutover_evidence ../docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`
   - repository evidence alone is not a tenant go-no-go artifact
   - для финального gate зафиксировать machine-readable `bundle_digest`

### Breaking / migration notes

- Legacy edge document_policy editor больше не является рекомендуемым net-new path; canonical route для новых policy revisions теперь `/decisions`.
- External/operator tooling не должно рассчитывать на database-local-only metadata context. Проверяйте `config_name`, `config_version` и diagnostics markers `config_generation_id`/`metadata_hash`/`publication_drift`, а не только `database_id`.
- Legacy snapshot/resolution state после backfill не должно ожидать отдельный canonical row на каждый `extensions_fingerprint`; shared state теперь canonicalize'ится только по business identity `config_name + config_version`.
- Historical decision rows и legacy metadata registry state должны быть прогнаны через `backfill_business_identity_state` до tenant cutover; без этого `/decisions` может честно оставаться fail-closed на `missing_metadata_context`.
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
- Live bundle contract: [workflow-hardening-rollout-evidence/README.md](../observability/artifacts/workflow-hardening-rollout-evidence/README.md)
- Cutover notes: [add-refactor-14-workflow-centric-hardening/cutover.md](/home/egor/code/command-center-1c/openspec/changes/archive/2026-03-12-add-refactor-14-workflow-centric-hardening/cutover.md)
