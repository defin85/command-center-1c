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
  Refresh/probe path, который материализует или переиспользует shared configuration-scoped snapshot для выбранной ИБ.
- `POST /api/v2/pools/<pool_id>/document-policy-migrations/`
  Deterministic import path `edge.metadata.document_policy -> decision resource + binding refs`.

## Hardened contract markers

- Новый `document_policy` authoring path идёт через `/decisions`, а не через direct edge editing как primary flow.
- `/templates` остаётся catalog atomic operations; workflow executor templates должны читаться как compatibility/integration path.
- `/pools/catalog` topology editor остаётся structural metadata surface; legacy edge `document_policy` editor read-only by default и открывается только как explicit compatibility action.
- Decision builder/import и migration path используют shared configuration-scoped snapshot provenance, а не database-local-only state. В ответах/API/UI ищи `snapshot_id`, `resolution_mode`, `metadata_hash`, `is_shared_snapshot`, `provenance_database_id`.

## Default operator flow

1. В `/workflows` проверь authored scheme library и убедись, что нужная схема есть в analyst-facing surface.
2. В `/templates` убедись, что workflow executor templates видны только как compatibility path, а нужные atomic operations доступны для composition.
3. В `/decisions` проверь, что нужная decision revision существует, активна и показывает ожидаемые metadata markers.
   Если metadata context ещё не прогрет, обнови snapshot через `POST /api/v2/pools/odata-metadata/catalog/refresh/` для representative database.
4. В `/pools/catalog` открой нужный pool и проверь active workflow bindings, effective period и selector scope.
   Default SPA path использует structured binding editor и first-class binding CRUD, а не raw JSON textarea.
5. Если на edge ещё жив legacy `document_policy`, выполни import в `/decisions` и зафиксируй resulting `Decision ref` / `Updated bindings`.
6. Перед canary или перед разбором инцидента запусти binding preview.
7. В `/pools/runs` стартуй run через явный `pool_workflow_binding_id`.
8. После старта проверь `Run Lineage / Operator Report`:
   - selected binding;
   - pinned workflow revision;
   - decision snapshot;
   - compiled runtime projection;
   - secondary link `Open Workflow Diagnostics`.

## Checked-in evidence templates

- Shared metadata snapshot evidence template:
  - `docs/observability/artifacts/refactor-14/shared-metadata-evidence.template.json`
- Legacy document_policy migration evidence template:
  - `docs/observability/artifacts/refactor-14/legacy-document-policy-migration-evidence.template.json`
- Operator canary evidence template:
  - `docs/observability/artifacts/refactor-14/operator-canary-evidence.template.json`

Templates are examples/placeholders only. They are meant to capture real cutover evidence and must not be committed as production rollout proof without replacing placeholders.

## Canary checklist

Перед rollout на tenant одновременно проверь:
- `/api/v2/workflows/list-workflows/` возвращает `authoring_phase` без unexpected deferred scope.
- `/api/v2/workflows/list-workflows/?surface=runtime_diagnostics` показывает projections отдельно от analyst library.
- `/api/v2/decisions/` и detail view показывают expected `snapshot_id`, `resolution_mode`, `metadata_hash`, `provenance_database_id`.
- Refresh representative infobase через `/api/v2/pools/odata-metadata/catalog/refresh/` не приводит к silent reuse при diverged metadata surface.
- `/templates` показывает compatibility marker для workflow executor templates и не выглядит как primary analyst-facing surface.
- Для production pool нет unintended active binding overlap по selector/effective period.
- Для legacy topology edges import через `/pools/catalog` или `POST /api/v2/pools/<pool_id>/document-policy-migrations/` создаёт decision revision и обновляет binding refs без ручного raw-id editing.
- Preview binding показывает ожидаемые workflow revision, decision refs и compile summary.
- Canary create-run проходит через `/api/v2/pools/runs/` с явным `pool_workflow_binding_id`.
- Public create-run/preview без `pool_workflow_binding_id` возвращают `POOL_WORKFLOW_BINDING_REQUIRED`; selector matching остаётся только pre-submit assistive UX.
- Inspect view на `/pools/runs` показывает lineage без необходимости уходить в generic workflow catalog.

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
- `resolution_mode` и `metadata_hash` в list/detail response;
- `provenance_database_id`, если snapshot должен быть shared между несколькими ИБ;
- refresh representative database через `POST /api/v2/pools/odata-metadata/catalog/refresh/`.

Если после refresh выбранная ИБ уходит в новый `snapshot_id`, это допустимо только при действительно diverged published metadata surface. Не возвращай вручную старый snapshot и не форсируй reuse только по совпадению `config_version`.

### 5. Legacy edge policy не импортируется в `/decisions`

Проверь:
- что child organization привязан к database;
- что metadata catalog для child database разрешён и валиден;
- что `POST /api/v2/pools/<pool_id>/document-policy-migrations/` не возвращает `POOL_DOCUMENT_POLICY_NOT_FOUND`, `POOL_METADATA_CONTEXT_REQUIRED` или metadata reference validation errors;
- что после import binding list действительно содержит новый decision ref.

Если import прошёл с `binding_update_required=true`, не продолжай rollout вслепую: сначала перепроверь binding refs и pin decision revision явно.

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
- [refactor-14 cutover.md](/home/egor/code/command-center-1c/openspec/changes/refactor-14-workflow-centric-hardening/cutover.md)
- [refactor-12 cutover.md](/home/egor/code/command-center-1c/openspec/changes/archive/2026-03-09-refactor-12-workflow-centric-analyst-modeling/cutover.md)
