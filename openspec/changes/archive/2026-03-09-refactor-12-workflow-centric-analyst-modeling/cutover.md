# Cutover / Rollback / Operator Diagnostics

## Цель
Этот runbook фиксирует управляемый переход на workflow-centric authoring для pools без второго source-of-truth и без неявного fallback.

Инварианты:
- analyst-facing source-of-truth для новых схем: `workflow definition` + decisions + `pool_workflow_binding`;
- primary operator surface для lifecycle и расследования: `/pools/runs`;
- generated runtime workflows остаются read-only diagnostics surface;
- rollback не переписывает исторические runs и не подменяет silently compiled runtime projection.

## Реальные рычаги cutover
Текущий код даёт два класса управляемых переключателей:

1. Rollout marker:
- runtime setting `workflows.authoring.phase`;
- поддерживаемые значения: `legacy_technical_dag`, `workflow_centric_prerequisite`, `workflow_centric_active`;
- настройка влияет на phase summary/UX-диагностику и не должна трактоваться как скрытый runtime fallback.

2. Runtime source selection:
- активные `pool_workflow_binding`;
- effective period (`effective_from` / `effective_to`);
- explicit binding selection в create-run payload через `pool_workflow_binding_id`.

Следствие: rollback выполняется через возврат rollout marker-а и через деактивацию/переключение bindings, а не через редактирование уже созданных runs.

## Go / No-Go Checklist
Перед cutover tenant считается готовым только если одновременно выполнено всё ниже:

1. `GET /api/v2/workflows/list-workflows/` возвращает authoring phase summary без unexpected deferred scope, а user-authored workflows остаются на `visibility_surface=workflow_library`.
2. `GET /api/v2/workflows/list-workflows/?surface=runtime_diagnostics` показывает system-managed runtime projections отдельно и в read-only режиме.
3. Для каждого production `pool` есть ровно один expected active binding на каждый selector/effective scope; неоднозначные bindings устранены до cutover.
4. Canary create-run проходит через `/api/v2/pools/runs/` с `pool_workflow_binding_id` и даёт lineage до workflow revision и decision snapshot.
5. Оператор может пройти сценарий inspect/confirm/retry из `/pools/runs` без перехода в generic workflow catalog как primary экран.
6. Publication preflight не показывает блокирующих mapping/auth проблем.

## Cutover Steps
1. Подготовить bindings.
   Для каждого `pool` оставить только intended active binding-и; новые bindings сначала заводить как `draft`/`inactive` либо с будущим `effective_from`.
2. Прогнать preflight.
   Минимум:
   - `orchestrator/venv/bin/python orchestrator/manage.py preflight_workflow_decommission_consumers --json`
   - `orchestrator/venv/bin/python orchestrator/manage.py preflight_pool_publication_auth_mapping`
3. Выполнить canary run на `/pools/runs`.
   Запускать через явный `pool_workflow_binding_id`, чтобы зафиксировать lineage и исключить selector ambiguity на первом включении.
4. Проверить operator diagnostics на canary.
   В inspect view должны быть:
   - `Run Lineage`;
   - pinned binding / workflow revision / decision refs;
   - `Underlying Workflow Runtime`;
   - secondary link `Open Workflow Diagnostics`.
5. Только после успешного canary опубликовать rollout marker.
   Для tenant override:
   - `PATCH /api/v2/settings/runtime-overrides/workflows.authoring.phase/`
   - body: `{"value":"workflow_centric_active","status":"published"}`
6. Перевести остальные intended bindings в `active` и оставить предыдущие ревизии неактивными либо закрытыми по effective window.

## Rollback Triggers
Rollback обязателен, если наблюдается хотя бы один сигнал:
- create-run или preview массово падают с `POOL_WORKFLOW_BINDING_REQUIRED`, `POOL_WORKFLOW_BINDING_NOT_RESOLVED`, `POOL_WORKFLOW_BINDING_NOT_FOUND` или `POOL_WORKFLOW_BINDING_INVALID`;
- canary/production runs строят неверный lineage между binding и runtime projection;
- confirm-publication системно блокируется readiness blockers без понятного remediation path;
- operators вынуждены уходить в generic workflow catalog для обычного lifecycle management;
- new binding revision даёт regression по runtime projection или downstream publication.

## Rollback Steps
1. Вернуть rollout marker на безопасную фазу:
   - `workflow_centric_prerequisite` для сохранения новых surfaces, но без сигнала “active”;
   - `legacy_technical_dag` только если нужно явно коммуницировать откат analyst-facing rollout.
   Этот шаг меняет phase summary и коммуникацию, но не переписывает существующие runs.
2. Деактивировать проблемный binding revision.
   Использовать `status=inactive` и/или закрыть effective window у нового binding.
3. Реактивировать last known good binding revision.
   Следующий run должен стартовать только через явный `pool_workflow_binding_id`.
   Selector matching остаётся только prefill/hint до submit, поэтому перед retry внешний клиент должен перечитать bindings или preview и отправить выбранный binding явно.
4. Не мутировать исторические runs.
   Расследование и операторская работа продолжаются на `/pools/runs`, потому что lineage/readiness/runtime diagnostics уже материализованы в read-model.
5. Если проблема касается только authoring UX, а runtime уже стабилен, оставить existing runs как есть и ограничить rollout только rollback marker-ом без попытки “пересобрать” прошлые runtime projections.

## Operator Diagnostics Map
### 1. Launch / Binding resolution
- Primary surface: `/pools/runs`
- Сигналы:
  - `POOL_WORKFLOW_BINDING_REQUIRED`
  - `POOL_WORKFLOW_BINDING_NOT_RESOLVED`
  - `POOL_WORKFLOW_BINDING_NOT_FOUND`
  - `POOL_WORKFLOW_BINDING_INVALID`
- Действие:
  - проверить selector/effective period у bindings и устранить overlap до submit;
  - всегда запускать run с явным `pool_workflow_binding_id` и не рассчитывать на server-side selector fallback.

### 2. Readiness / Safe commands
- Primary surface: `/pools/runs` inspect
- Сигналы:
  - `readiness_blockers`
  - `readiness_checklist`
  - `master_data_gate`
  - confirm-publication problem details
- Действие:
  - идти по remediation hints (`Open Bindings workspace`, master-data remediation links);
  - не обходить blockers вручную через secondary workflow screens.

### 3. Runtime / Execution diagnostics
- Primary surface: `/pools/runs` inspect
- Secondary surface: `/workflows?surface=runtime_diagnostics`
- Сигналы:
  - `Underlying Workflow Runtime`
  - `retry_chain`
  - workflow status / workflow execution id
  - merged run diagnostics payload
- Действие:
  - сначала смотреть lineage и runtime summary в `/pools/runs`;
  - в runtime diagnostics surface переходить только для engine-level расследования.

### 4. Authoring surface separation
- Analyst library: `/workflows`
- Diagnostics-only runtime surface: `/workflows?surface=runtime_diagnostics`
- Ожидаемое поведение:
  - user-authored definitions редактируемы;
  - system-managed runtime projections read-only и не выступают primary authoring screen.

## Что не считается rollback
- Ручное редактирование historical run payloads.
- Скрытый fallback к raw edge-level `document_policy` authoring для новых сценариев.
- Молчаливый выбор одного binding при ambiguity.
- Перенос операторов на generic workflow catalog как основной operational UI.
