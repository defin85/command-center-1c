# Workflow-centric Pools Runbook

Цель: дать operator-facing и support-facing runbook для workflow-centric authoring/modeling pools на реальном shipped path.

## Канонические surfaces

- Analyst library: `/workflows`
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

## Default operator flow

1. В `/workflows` проверь authored scheme library и убедись, что нужная схема есть в analyst-facing surface.
2. В `/pools/catalog` открой нужный pool и проверь active workflow bindings, effective period и selector scope.
   Default SPA path использует structured binding editor и first-class binding CRUD, а не raw JSON textarea.
3. Перед canary или перед разбором инцидента запусти binding preview.
4. В `/pools/runs` стартуй run через явный `pool_workflow_binding_id`.
5. После старта проверь `Run Lineage / Operator Report`:
   - selected binding;
   - pinned workflow revision;
   - decision snapshot;
   - compiled runtime projection;
   - secondary link `Open Workflow Diagnostics`.

## Canary checklist

Перед rollout на tenant одновременно проверь:
- `/api/v2/workflows/list-workflows/` возвращает `authoring_phase` без unexpected deferred scope.
- `/api/v2/workflows/list-workflows/?surface=runtime_diagnostics` показывает projections отдельно от analyst library.
- Для production pool нет unintended active binding overlap по selector/effective period.
- Preview binding показывает ожидаемые workflow revision, decision refs и compile summary.
- Canary create-run проходит через `/api/v2/pools/runs/` с явным `pool_workflow_binding_id`.
- Inspect view на `/pools/runs` показывает lineage без необходимости уходить в generic workflow catalog.

## Частые ошибки binding resolution

- `POOL_WORKFLOW_BINDING_AMBIGUOUS`
  Для одного pool найдено несколько active binding под один direction/mode/scope. Устрани overlap или запускай run с явным `pool_workflow_binding_id`.
- `POOL_WORKFLOW_BINDING_NOT_RESOLVED`
  Под selected period/direction/mode нет подходящего active binding или выбранный binding inactive.
- `POOL_WORKFLOW_BINDING_NOT_FOUND`
  Клиент отправил неизвестный `pool_workflow_binding_id`.
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

Preview и runtime start должны использовать один и тот же schema-template resolution path.
Если `schema_template_id` не передан, оба пути должны резолвить managed default schema template `__runtime-default__`.

### 3. Operator не видит lineage на `/pools/runs`

Проверь:
- что run создан через workflow-centric path, а не legacy historical contract;
- наличие `workflow_binding` и `runtime_projection` в run read-model;
- secondary link `Open Workflow Diagnostics` для engine-level расследования.

## Rollback

Rollback выполняется без переписывания historical runs:

1. Верни rollout marker на `workflow_centric_prerequisite` или `legacy_technical_dag`.
2. Деактивируй проблемный binding revision или закрой effective window.
3. Реактивируй last-known-good binding revision.
4. Продолжай расследование через `/pools/runs` и diagnostics surface.

## Связанные материалы

- [OPERATORS_SPA_GUIDE.md](../OPERATORS_SPA_GUIDE.md)
- [2026-02-15-pools-run-input-breaking-change.md](../release-notes/2026-02-15-pools-run-input-breaking-change.md)
- [refactor-12 cutover.md](/home/egor/code/command-center-1c/openspec/changes/archive/2026-03-09-refactor-12-workflow-centric-analyst-modeling/cutover.md)
