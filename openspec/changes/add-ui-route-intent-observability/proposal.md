# Change: Semantic route intent and loop diagnostics for UI observability

## Why
Текущий replay-free observability contour уже хорошо показывает симптомы UI-инцидента: route transitions, synthetic request boundaries, `request_id` / `ui_action_id`, slow/failure HTTP и WebSocket churn. Этого хватает, чтобы увидеть, что проблема произошла, но не всегда хватает, чтобы быстро понять, какой именно operator intent её запустил и какой route writer потом начал переписывать URL.

Свежий инцидент в `/pools/master-data` это показал явно:
- contour честно зафиксировал oscillation между `tab=bindings` и `tab=sync`, серию `429 RATE_LIMIT_EXCEEDED` по `sync-status` и slow reads по `sync-target-databases`;
- contour не смог доказательно ответить, какой route-changing control был нажат последним;
- contour не смог отделить пользовательский intent от вторичных `setSearchParams(...)` writers внутри route-owned shell и дочерних tab surfaces.

Нужен узкий residual change, который усилит существующий observability contract без перехода к DOM/session replay:
- explicit semantic route intent для route-changing controls;
- route-write attribution для instrumented route writers;
- bounded machine-readable loop warning, когда route начинает осциллировать.

## What Changes
- Расширить capability `ui-action-observability`, чтобы route-changing operator controls писали explicit semantic intent с устойчивыми `surface_id` / `control_id` и route context `from -> to`.
- Зафиксировать route-write attribution contract для instrumented route-owned surfaces и child writers: `route_writer_owner`, `write_reason`, `navigation_mode`, `caused_by_ui_action_id`, bounded `param_diff`.
- Зафиксировать bounded `route.loop_warning` signal для oscillation/loop сценариев вместо необходимости вручную реконструировать цикл по десяткам `route.transition`.
- Считать `Pool Master Data` первой обязательной delivery surface для этого change:
  - route-owned shell в `PoolMasterDataPage`;
  - child route writers в `SyncStatusTab` и `DedupeReviewTab`;
  - operator-facing zone switches `Bindings` / `Sync` как confirmed pilot path.
- Расширить `agent-ui-observability-access`, чтобы default agent monitoring path видел не только route/error chronology, но и semantic route intent, route-writer attribution и loop warning без screen scraping product UI.

## Impact
- Affected specs:
  - `ui-action-observability`
  - `agent-ui-observability-access`
- Related existing specs/changes:
  - `add-ui-incident-telemetry-pipeline` остаётся durable producer/storage substrate и не дублируется этим change
  - `add-gateway-request-budget-isolation` остаётся source of truth для machine-readable `429` metadata и budget diagnostics
- Affected code:
  - `frontend/src/observability/uiActionJournal.ts`
  - `frontend/src/observability/uiIncidentTelemetry.ts`
  - `frontend/src/pages/Pools/PoolMasterDataPage.tsx`
  - `frontend/src/pages/Pools/masterData/SyncStatusTab.tsx`
  - `frontend/src/pages/Pools/masterData/DedupeReviewTab.tsx`
  - `orchestrator/apps/monitoring/ui_incident_telemetry.py`
  - `orchestrator/apps/api_v2/views/ui_incident_telemetry.py`
  - `contracts/orchestrator/**`
  - `debug/export-ui-journal.sh`, `debug/query-ui-incidents.sh`, `debug/query-ui-timeline.sh` (если query payload shape потребует расширения)

## Non-Goals
- Не вводить raw DOM replay, video/session replay или запись координат кликов.
- Не писать каждый `click` / `keypress` в product UI.
- Не логировать произвольные button labels, innerText или не-whitelisted form values как замену semantic IDs.
- Не пытаться в этом change инструментировать все route-changing controls во всей SPA; first delivery scope bounded around `Pool Master Data`.
- Не лечить сами `429`/budget issues или route loop root cause автоматически; change только делает их быстрее diagnosable.
