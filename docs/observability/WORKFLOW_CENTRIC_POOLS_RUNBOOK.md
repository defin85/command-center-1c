# Workflow-centric Pools Runbook

Цель: дать operator-facing и support-facing runbook для workflow-centric authoring/modeling pools на реальном shipped path.

## Канонические surfaces

- Analyst library: `/workflows`
- Decision lifecycle / migration: `/decisions`
- Atomic operations catalog: `/templates`
- Runtime diagnostics: `/workflows?surface=runtime_diagnostics`
- Pool binding authoring: `/pools/catalog`
- Pool run launch and lineage: `/pools/runs`

## Rollout marker

Runtime key: `workflows.authoring.phase`

Поддерживаемые значения:
- `legacy_technical_dag`
- `workflow_centric_prerequisite`
- `workflow_centric_active`

Checked-in default:
- `workflow_centric_prerequisite`

Marker влияет на phase summary и rollout communication. Он не переключает runtime execution на скрытый fallback path.

## Реальные API endpoints

- `GET /api/v2/workflows/list-workflows/`
  Возвращает authored workflow library и `authoring_phase`.
- `GET /api/v2/workflows/list-workflows/?surface=runtime_diagnostics`
  Возвращает system-managed runtime projections в read-only diagnostics surface.
- `PATCH /api/v2/settings/runtime-overrides/workflows.authoring.phase/`
  Tenant override для rollout marker.
- `GET /api/v2/pools/workflow-bindings/?pool_id=<uuid>`
  First-class list of workflow bindings for one pool.
- `POST /api/v2/pools/workflow-bindings/upsert/`
  First-class create/update path for one pool binding.
- `GET /api/v2/pools/workflow-bindings/<binding_id>/?pool_id=<uuid>`
  Read one pinned binding in pool scope.
- `DELETE /api/v2/pools/workflow-bindings/<binding_id>/?pool_id=<uuid>`
  Deactivate/remove one binding from pool scope.
- `POST /api/v2/pools/runs/`
  Канонический create-run endpoint.
- `POST /api/v2/pools/workflow-bindings/preview/`
  Preview effective binding/runtime projection до старта run.
- `GET /api/v2/decisions/`
  First-class list/detail surface для versioned `document_policy` decision resources.
- `POST /api/v2/decisions/`
  Create/revise/deactivate decision revision c metadata-aware validation context.
- `POST /api/v2/pools/odata-metadata/catalog/refresh/`
  Refresh/probe path, который материализует или переиспользует canonical business-scoped snapshot для выбранной ИБ.
- `POST /api/v2/pools/<pool_id>/document-policy-migrations/`
  Deterministic import path `edge.metadata.document_policy -> decision resource + binding refs`.

## Hardened contract markers

- Новый `document_policy` authoring path идёт через `/decisions`, а не через direct edge editing как primary flow.
- В `/decisions` canonical edge migration идёт через action `Import legacy edge`; `Import raw JSON` остаётся explicit compatibility-only fallback.
- `/templates` остаётся catalog atomic operations; workflow executor templates должны читаться как compatibility/integration path.
- `/pools/catalog` topology editor остаётся structural metadata surface; legacy edge `document_policy` editor read-only by default и открывается только как explicit compatibility action.
- Decision builder/import и migration path используют business configuration identity provenance, а не database-local-only state. В ответах/API/UI ищи `config_name`, `config_version`, `config_generation_id`, `metadata_hash`, `observed_metadata_hash`, `publication_drift`, `is_shared_snapshot`, `provenance_database_id`.

## Default operator flow

1. В `/workflows` проверь authored scheme library и убедись, что нужная схема есть в analyst-facing surface.
   Если схема использует reusable subprocess, проверь pinned subworkflow metadata: node должен оставаться привязанным к явной revision, а не к mutable latest.
2. В `/templates` убедись, что workflow executor templates видны только как compatibility path, а нужные atomic operations доступны для composition.
3. В `/decisions` проверь, что нужная decision revision существует, активна и показывает ожидаемые metadata markers.
   Если metadata context ещё не прогрет, обнови snapshot через `POST /api/v2/pools/odata-metadata/catalog/refresh/` для representative database.
   Если rollout поднимается с legacy snapshot/resolution или historical decision rows, сначала прогоняй one-time backfill:
   - `cd orchestrator && ./venv/bin/python manage.py backfill_business_identity_state --dry-run --json`
   - apply-run после dry-run: `cd orchestrator && ./venv/bin/python manage.py backfill_business_identity_state --json`
   - Команда canonicalize'ит legacy infobase-scoped snapshot/resolution rows по business identity `config_name + config_version`; `extensions_fingerprint` остаётся только diagnostics marker и не делит canonical state.
   - Для shipped contract одинаковая business identity `config_name + config_version` определяет reuse, а `metadata_hash`/`publication_drift` остаются diagnostics-only markers.
4. В `/pools/catalog` открой нужный pool и проверь active workflow bindings, effective period и selector scope.
   Default SPA path использует structured binding editor и first-class binding CRUD, а не raw JSON textarea.
5. Если на edge ещё жив legacy `document_policy`, выполни canonical import в `/decisions`:
   - UI: `/decisions` -> `Import legacy edge`
   - explicit compatibility-only fallback: `/decisions` -> `Import raw JSON`
   - compatibility shortcut: `/pools/catalog` -> `Import to /decisions`
   - deterministic API: `POST /api/v2/pools/<pool_id>/document-policy-migrations/`
   Зафиксируй resulting `Decision ref` / `Updated bindings`.
6. Перед canary или перед разбором инцидента запусти binding preview.
7. В `/pools/runs` стартуй run через явный `pool_workflow_binding_id`.
8. После старта проверь `Run Lineage / Operator Report`:
   - selected binding;
   - pinned workflow revision;
   - decision snapshot;
   - compiled runtime projection;
   - secondary link `Open Workflow Diagnostics`.

## Checked-in repository acceptance evidence

- Default shipped path proof:
  - `docs/observability/artifacts/refactor-14/repository-acceptance-evidence.md`

Repository acceptance evidence is the canonical checked-in proof path for shipped behavior inside git.
repository acceptance evidence не заменяет tenant live cutover evidence bundle.

## Checked-in operator evidence templates

- Shared metadata snapshot evidence template:
  - `docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json`
- Legacy document_policy migration evidence template:
  - `docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json`
- Operator canary evidence template:
  - `docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json`

Templates are examples/placeholders only. They are meant to capture tenant-scoped live cutover evidence and must not be committed as production rollout proof without replacing placeholders.

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
- Прогони `verify_workflow_hardening_cutover_evidence` и зафиксируй `bundle_digest` из machine-readable verdict.
- Не считай checked-in templates или repository proof заменой live tenant artifact.

## Canary checklist

Перед rollout на tenant одновременно проверь:
- `/api/v2/workflows/list-workflows/` возвращает `authoring_phase` без unexpected deferred scope.
- `/api/v2/workflows/list-workflows/?surface=runtime_diagnostics` показывает projections отдельно от analyst library.
- `/api/v2/decisions/` и detail view показывают expected `config_name`, `config_version`, `config_generation_id`, `metadata_hash`, `publication_drift`, `provenance_database_id`.
- One-time command `backfill_business_identity_state` не возвращает unexpected unresolved rows для pilot tenant.
- One-time command `backfill_business_identity_state` схлопывает legacy rows с одинаковой business identity даже при разном `extensions_fingerprint`; fingerprint после этого проверяется только как diagnostics marker.
- Refresh representative infobase через `/api/v2/pools/odata-metadata/catalog/refresh/` сохраняет reuse по одинаковой business identity `config_name + config_version`; при diverged metadata surface API/UI показывают publication drift diagnostics и canonical shared snapshot provenance.
- `/templates` показывает compatibility marker для workflow executor templates и не выглядит как primary analyst-facing surface.
- Для production pool нет unintended active binding overlap по selector/effective period.
- Canonical legacy-edge import через `/decisions` -> `Import legacy edge` создаёт decision revision и обновляет binding refs без ручного raw-id editing.
- `/decisions` -> `Import raw JSON` остаётся explicit compatibility-only fallback и не подменяет canonical edge migration.
- Compatibility shortcut через `/pools/catalog` -> `Import to /decisions` использует тот же deterministic migration contract.
- Preview binding показывает ожидаемые workflow revision, decision refs и compile summary.
- Canary create-run проходит через `/api/v2/pools/runs/` с явным `pool_workflow_binding_id`.
- Public create-run/preview без `pool_workflow_binding_id` возвращают `POOL_WORKFLOW_BINDING_REQUIRED`; selector matching остаётся только pre-submit assistive UX.
- Inspect view на `/pools/runs` показывает lineage без необходимости уходить в generic workflow catalog.
- Для reusable subprocess path `/workflows` и runtime diagnostics сохраняют pinned subworkflow revision; conflicting `subworkflow_id`/`subworkflow_ref` не должен silently repair'иться до latest revision.

## Частые ошибки binding resolution

- `POOL_WORKFLOW_BINDING_REQUIRED`
  Клиент не передал `pool_workflow_binding_id`. Public create-run/preview не делают selector fallback, даже если по selector есть ровно один кандидат.
- `POOL_WORKFLOW_BINDING_NOT_RESOLVED`
  Под selected period/direction/mode нет подходящего active binding или выбранный binding inactive.
- `POOL_WORKFLOW_BINDING_NOT_FOUND`
  Клиент отправил неизвестный `pool_workflow_binding_id` или binding не принадлежит выбранному pool.
- `POOL_WORKFLOW_BINDING_INVALID`
  Stored binding payload в pool не проходит contract validation.

## Troubleshooting

### 1. Analyst library смешивается с runtime projections

Проверь:
- query param `surface=runtime_diagnostics`;
- что пользователь открыл `/workflows`, а не diagnostics surface;
- `authoring_phase` в `GET /api/v2/workflows/list-workflows/`.

### 2. Preview и create-run ведут себя по-разному

Проверь:
- одинаковый `pool_workflow_binding_id`;
- одинаковый `direction`, `mode`, `period_start`, `period_end`, `run_input`;
- совпадает ли `schema_template_id`, если он указан явно.
- Если `pool_workflow_binding_id` не передан, и preview, и create-run должны одинаково завершаться `POOL_WORKFLOW_BINDING_REQUIRED`.

Preview и runtime start должны использовать один и тот же schema-template resolution path.
Если `schema_template_id` не передан, оба пути должны резолвить managed default schema template `__runtime-default__`.

### 3. Operator не видит lineage на `/pools/runs`

Проверь:
- что run создан через workflow-centric path, а не legacy historical contract;
- наличие `workflow_binding` и `runtime_projection` в run read-model;
- secondary link `Open Workflow Diagnostics` для engine-level расследования.

### 4. `/decisions` показывает неожиданный metadata context

Проверь:
- `config_name`, `config_version`, `config_generation_id`, `metadata_hash`, `observed_metadata_hash` и `publication_drift` в list/detail response;
- `provenance_database_id`, если snapshot должен быть shared между несколькими ИБ;
- refresh representative database через `POST /api/v2/pools/odata-metadata/catalog/refresh/`.
- one-time backfill state:
  - `cd orchestrator && ./venv/bin/python manage.py backfill_business_identity_state --dry-run --json`
  - если dry-run показывает только ожидаемые rows, повтори без `--dry-run`.

Если после refresh выбранная ИБ показывает `publication_drift=true` или другой `observed_metadata_hash`, это допустимый diagnostics signal при общей business identity. Отдельный `snapshot_id` ожидаем только когда меняется сама business identity либо canonical snapshot ещё не materialized; не считай drift причиной для manual incompatibility, пока совпадают `config_name + config_version`.

### 5. Legacy edge policy не импортируется в `/decisions`

Проверь:
- что child organization привязан к database;
- что metadata catalog для child database разрешён и валиден;
- что `POST /api/v2/pools/<pool_id>/document-policy-migrations/` не возвращает `POOL_DOCUMENT_POLICY_NOT_FOUND`, `POOL_METADATA_CONTEXT_REQUIRED` или metadata reference validation errors;
- что после import binding list действительно содержит новый decision ref.

Если import прошёл с `binding_update_required=true`, не продолжай rollout вслепую: сначала перепроверь binding refs и pin decision revision явно.

### 6. Pinned subworkflow ведёт себя как latest revision

Проверь:
- что node config содержит `subworkflow_ref(binding_mode="pinned_revision")`, а `workflow_revision_id` в ref совпадает с compatibility field `subworkflow_id`;
- что `/workflows` показывает pinned revision в node details и не пересохраняет её молча при открытии editor;
- что runtime diagnostics и lineage продолжают ссылаться на ту же pinned subworkflow revision.

Если metadata drifted/conflicting, runtime должен завершаться fail-closed. Не переключай subworkflow вручную на latest revision как workaround.

## Rollback

Rollback выполняется без переписывания historical runs:

1. Верни rollout marker на `workflow_centric_prerequisite` или `legacy_technical_dag`.
2. Деактивируй проблемный binding revision или закрой effective window.
3. Реактивируй last-known-good binding revision.
4. Не возвращай legacy edge `document_policy` editor в primary authoring path для net-new сценариев; legacy compatibility surface остаётся только для controlled rollback window и audit.
5. Продолжай расследование через `/pools/runs`, `/decisions` и diagnostics surface.

## Связанные материалы

- [OPERATORS_SPA_GUIDE.md](../OPERATORS_SPA_GUIDE.md)
- [2026-02-15-pools-run-input-breaking-change.md](../release-notes/2026-02-15-pools-run-input-breaking-change.md)
- [2026-03-10-workflow-centric-hardening-cutover.md](../release-notes/2026-03-10-workflow-centric-hardening-cutover.md)
- [add-refactor-14-workflow-centric-hardening/cutover.md](/home/egor/code/command-center-1c/openspec/changes/archive/2026-03-12-add-refactor-14-workflow-centric-hardening/cutover.md)
- [refactor-12 cutover.md](/home/egor/code/command-center-1c/openspec/changes/archive/2026-03-11-refactor-12-workflow-centric-analyst-modeling/cutover.md)
