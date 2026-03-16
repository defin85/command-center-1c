# Cutover Notes / Rollback Window

Change: `refactor-14-workflow-centric-hardening`

## Canonical references

- Operator runbook: `docs/observability/WORKFLOW_CENTRIC_POOLS_RUNBOOK.md`
- Release notes: `docs/release-notes/2026-03-10-workflow-centric-hardening-cutover.md`
- Repository acceptance evidence: `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md`

## Checked-in evidence sources

- Repository acceptance evidence proves the shipped default path inside git:
  - `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md`
- Tenant-scoped live cutover capture may start from checked-in templates/examples:
  - `docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json`
  - `docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json`
  - `docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json`

Repository acceptance evidence не заменяет tenant live cutover evidence bundle.
Templates/examples are inputs only and are not sufficient for staging/prod go-no-go.

## Tenant live cutover evidence bundle

- Stable artifact root:
  - `docs/observability/artifacts/workflow-hardening-rollout-evidence/`
- Default live bundle location:
  - `docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`
- Verifier:
  - `cd orchestrator && ../.venv/bin/python manage.py verify_workflow_hardening_cutover_evidence ../docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`

Перед staging/prod go-no-go:
- Сверь repository proof в `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md`.
- Собери tenant-scoped live bundle по стабильному path.
- Прогони `verify_workflow_hardening_cutover_evidence` и зафиксируй machine-readable `bundle_digest`.
- Не считай checked-in templates/examples или repository proof заменой live tenant artifact.

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
3. Business identity backfill dry-run не даёт неожиданных unresolved rows:
   - `cd orchestrator && ./venv/bin/python manage.py backfill_business_identity_state --dry-run --json`
4. Publication auth mapping preflight для pilot tenant не даёт blocking ошибок:
   - `cd orchestrator && ./venv/bin/python manage.py preflight_pool_publication_auth_mapping --strict`
5. Для каждого pilot tenant выбран representative database на каждую configuration profile.

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

Перед refresh/probe path прогоняй one-time business identity backfill для legacy snapshot/resolution rows и historical decision metadata:

```bash
cd orchestrator && ./venv/bin/python manage.py backfill_business_identity_state --json
```

Shared registry потом гидратируется через refresh/probe path на representative infobase.

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
6. Shared metadata evidence template является capture input only; staging/prod go-no-go выполняется только через tenant live bundle.

## Stage 3: Legacy document_policy migration

Для каждого pool/edge, где legacy `edge.metadata.document_policy` ещё нужен в runtime path:

1. Предпочтительный operator path:
   - `/decisions` -> `Import legacy edge`
   - explicit compatibility-only fallback: `/decisions` -> `Import raw JSON`
   - compatibility handoff: `/pools/catalog` -> remediation alert -> `Open /decisions`
2. Deterministic API path:
   - `POST /api/v2/pools/<pool_id>/document-policy-migrations/`
3. Зафиксировать outcome:
   - `Decision ref`
   - `Updated bindings`
   - metadata context (`snapshot_id`, `resolution_mode`, `metadata_hash`)
4. Если ответ вернул `binding_update_required=true`, не переходить к tenant cutover, пока binding refs не закреплены явно.
5. Для фиксации evidence используй checked-in template:
   - `docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json`
6. Migration evidence template является capture input only; финальный gate использует tenant live bundle с machine-readable outcome.

## Stage 4: Tenant-scoped cutover

1. Global baseline оставить на `workflow_centric_prerequisite`.
2. Для pilot tenant включить marker:
   - `PATCH /api/v2/settings/runtime-overrides/workflows.authoring.phase/`
   - Header: `X-CC1C-Tenant-ID: <pilot-tenant-id>`
   - Payload: `{"value":"workflow_centric_active","status":"published"}`
3. Проверить surfaces:
   - `/workflows` показывает analyst composition guidance;
   - reusable subprocess nodes в `/workflows` сохраняют pinned subworkflow revision и не теряют `subworkflow_ref(binding_mode="pinned_revision")`;
   - `/templates` показывает compatibility marker;
   - `/decisions` показывает metadata provenance;
   - `/decisions` остаётся canonical legacy import surface;
   - `/decisions` -> `Import raw JSON` остаётся explicit compatibility-only fallback;
   - `/pools/catalog` даёт только remediation handoff в `/decisions` для legacy policy migration;
   - `/pools/runs` показывает pinned decision refs и workflow diagnostics link.
4. Выполнить pilot canary run и inspect.
   Следующий run должен стартовать только через явный `pool_workflow_binding_id`.
   Для фиксации preview/create-run/inspect evidence используй:
   - `docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json`
5. После capture inputs собрать tenant-scoped live bundle:
   - `docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`
   - verifier: `cd orchestrator && ../.venv/bin/python manage.py verify_workflow_hardening_cutover_evidence ../docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`
   - repository acceptance evidence не заменяет tenant live cutover evidence bundle
   - templates/examples are inputs only and are not sufficient for staging/prod go-no-go
   - для финального gate зафиксировать machine-readable `bundle_digest`
6. После `status=passed` и `go_no_go=go` расширять rollout батчами tenant-ов.

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
- reusable subprocess path подтверждает pinned subworkflow fail-closed behaviour на checked-in shipped path;
- shared metadata snapshot evidence собран по каждой configuration profile;
- legacy document_policy migration outcome зафиксирован для всех pilot pools;
- tenant live cutover evidence bundle проходит verifier и зафиксирован с machine-readable `bundle_digest`;
- rollback window либо закрыт после успешного first scale-out batch, либо остаётся открытым с documented follow-up.
