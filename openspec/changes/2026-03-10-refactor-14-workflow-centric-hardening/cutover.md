# Cutover Notes / Rollback Window

Change: `refactor-14-workflow-centric-hardening`

## Canonical references

- Operator runbook: `docs/observability/WORKFLOW_CENTRIC_POOLS_RUNBOOK.md`
- Release notes: `docs/release-notes/2026-03-10-workflow-centric-hardening-cutover.md`
- Repository acceptance evidence: `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md`

## Checked-in evidence sources

- Repository acceptance evidence proves the shipped default path inside git:
  - `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md`
- Tenant-scoped live cutover capture uses checked-in templates/examples:
  - `docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json`
  - `docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json`
  - `docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json`

## Goal

Выполнить tenant-scoped cutover на hardened workflow-centric contract без post-cutover runtime fallback:
- canonical pool bindings читаются из first-class store, а не из `pool.metadata["workflow_bindings"]`;
- new `document_policy` authoring идёт через `/decisions`;
- shared metadata snapshots резолвятся по configuration scope/signature;
- `/templates` и legacy edge editor остаются compatibility surface, а не primary authoring path.

## Preflight / No-Go

Cutover нельзя начинать, если любой из пунктов ниже не выполнен:

1. Backend/frontend с route-ами `/decisions`, `/workflows`, `/templates`, `/pools/catalog`, `/pools/runs` уже задеплоены.
2. Binding backfill dry-run не даёт неожиданных remediation items:
   - `cd orchestrator && ./venv/bin/python manage.py backfill_pool_workflow_bindings --dry-run --json`
   - допустимые причины для явной ручной remediation:
     - `invalid_legacy_binding`
     - `conflicting_canonical_binding`
     - `canonical_only_binding`
3. Publication auth mapping preflight для pilot tenant не даёт blocking ошибок:
   - `cd orchestrator && ./venv/bin/python manage.py preflight_pool_publication_auth_mapping --strict`
4. Для каждого pilot tenant выбран representative database на каждую configuration profile.

## Stage 1: Canonical binding backfill

1. Dry-run:

```bash
cd orchestrator && ./venv/bin/python manage.py backfill_pool_workflow_bindings --dry-run --json
```

2. Устранить remediation items до apply-run.
3. Apply-run:

```bash
cd orchestrator && ./venv/bin/python manage.py backfill_pool_workflow_bindings --json
```

4. Критерий завершения Stage 1:
   - pilot pools читают bindings через `/api/v2/pools/workflow-bindings/`;
   - `pool upsert` больше не требуется для migration canonical bindings;
   - unresolved remediation items не остаются на pilot tenant.

## Stage 2: Shared metadata snapshot warm-up

В этом change нет отдельного bulk CLI для metadata registry. Shared registry гидратируется через refresh/probe path на representative infobase.

Для каждой configuration profile:

1. Выполнить refresh:
   - `POST /api/v2/pools/odata-metadata/catalog/refresh/`
2. Зафиксировать в evidence:
   - `database_id`
   - `snapshot_id`
   - `resolution_mode`
   - `metadata_hash`
   - `provenance_database_id`
3. Если expected shared profile возвращает `resolution_mode=shared_scope`, reuse считается валидным.
4. Если refresh даёт новый `snapshot_id` при том же `config_version`, трактовать это как допустимый divergence только после проверки фактического `metadata_hash`/published metadata surface.
5. Для фиксации evidence используй checked-in template:
   - `docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json`

## Stage 3: Legacy document_policy migration

Для каждого pool/edge, где legacy `edge.metadata.document_policy` ещё нужен в runtime path:

1. Предпочтительный operator path:
   - `/pools/catalog` -> `Topology Editor` -> `Import to /decisions`
2. Deterministic API path:
   - `POST /api/v2/pools/<pool_id>/document-policy-migrations/`
3. Зафиксировать outcome:
   - `Decision ref`
   - `Updated bindings`
   - metadata context (`snapshot_id`, `resolution_mode`, `metadata_hash`)
4. Если ответ вернул `binding_update_required=true`, не переходить к tenant cutover, пока binding refs не закреплены явно.
5. Для фиксации evidence используй checked-in template:
   - `docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json`

## Stage 4: Tenant-scoped cutover

1. Global baseline оставить на `workflow_centric_prerequisite`.
2. Для pilot tenant включить marker:
   - `PATCH /api/v2/settings/runtime-overrides/workflows.authoring.phase/`
   - Header: `X-CC1C-Tenant-ID: <pilot-tenant-id>`
   - Payload: `{"value":"workflow_centric_active","status":"published"}`
3. Проверить surfaces:
   - `/workflows` показывает analyst composition guidance;
   - `/templates` показывает compatibility marker;
   - `/decisions` показывает metadata provenance;
   - `/pools/catalog` импортирует legacy policy без direct edge authoring как primary path;
   - `/pools/runs` показывает pinned decision refs и workflow diagnostics link.
4. Выполнить pilot canary run и inspect.
   Следующий run должен стартовать только через явный `pool_workflow_binding_id`.
   Для фиксации preview/create-run/inspect evidence используй:
   - `docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json`
5. После green pilot расширять rollout батчами tenant-ов.

## Rollback window

Rollback window остаётся открытым до завершения pilot tenant и первого scale-out batch.

В течение этого окна:
- не удалять previous binding revisions, даже если они inactive;
- не очищать legacy edge metadata, пока import evidence не зафиксирован;
- не считать migration завершённой без сохранённых `snapshot_id`, `Decision ref`, `Updated bindings`.

## Rollback

1. Вернуть tenant override `workflows.authoring.phase` на `workflow_centric_prerequisite`.
2. Деактивировать проблемный binding revision и реактивировать last-known-good binding.
3. Legacy edge `document_policy` не возвращать в primary authoring path; compatibility editor остаётся только как controlled remediation surface.
4. Следующий run должен стартовать только через явный `pool_workflow_binding_id`.
5. Historical runs не переписывать; расследование вести через `/pools/runs` и workflow diagnostics.

## Exit criteria

- bindings читаются только через canonical CRUD/read-model;
- pilot tenant использует `/decisions` как primary policy surface;
- shared metadata snapshot evidence собран по каждой configuration profile;
- legacy document_policy migration outcome зафиксирован для всех pilot pools;
- rollback window либо закрыт после успешного first scale-out batch, либо остаётся открытым с documented follow-up.
