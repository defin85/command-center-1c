# Change: Добавить staff-only runtime control plane и control surfaces в `/system-status`

## Why
Сейчас в checked-in UI нет единого operator path для управления runtime-процессами и scheduler jobs:
- `/system-status` и `/service-mesh` дают observability, но не lifecycle control;
- `/settings/runtime` редактирует generic runtime settings, но не является control console;
- `/pools/factual` умеет только узкий `Refresh factual sync` для конкретного pool/quarter;
- factual scheduler живёт в `worker-workflows` и в основном управляется startup env (`ENABLE_GO_SCHEDULER`), а не live control plane.

При этом в репозитории уже есть allowlisted local runtime inventory и restart/probe helpers (`debug/runtime-inventory.sh`, `debug/restart-runtime.sh`), а также модель `SchedulerJobRun` для истории scheduler runs. Не хватает permissioned и audited control plane, который:
- не превращается в generic remote shell;
- разделяет observed state, desired state и imperative action;
- даёт staff оператору один понятный UI path для runtime/scheduler management.

## What Changes
- Ввести новый capability `runtime-control-plane` для allowlisted runtime catalog со stable runtime instance identity, provider-backed actions, async action runs, desired scheduler state и operator audit trail.
- Расширить `infra-observability-workspaces`, чтобы `/system-status` оставался primary route для runtime inspection и получал deep-linkable runtime drill-down (`Overview`, `Controls`, `Scheduler`, `Logs`) для privileged operators.
- Расширить `settings-management-workspaces`, чтобы `/settings/runtime` оставался advanced settings workspace и принимал declarative runtime/scheduler policy keys по deep-link из `/system-status`, не дублируя live process controls.
- Расширить `runtime-settings-overrides`, чтобы runtime-control/scheduler keys оставались global-only и не попадали в tenant override APIs/effective tenant resolution.
- Добавить dedicated runtime-control permission и shell capability вместо implicit staff-only affordances.
- Зафиксировать, что `trigger_now` для scheduler jobs коррелируется с scheduler run history и не подменяет domain-specific actions вроде `Refresh factual sync` в `/pools/factual`.
- Зафиксировать provider model: local/hybrid backend может использовать checked-in runtime inventory/restart/probe helpers, а production/provider-specific integrations должны приходить за тем же API contract без arbitrary shell execution и без утечки unredacted log/output payloads в UI.

## Impact
- Affected specs:
  - `infra-observability-workspaces`
  - `settings-management-workspaces`
  - `runtime-settings-overrides`
  - `runtime-control-plane` (new)
- Affected code (expected, when implementing this change):
  - `frontend/src/pages/SystemStatus/**`
  - `frontend/src/pages/Settings/RuntimeSettingsPage.tsx`
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/authz/**`
  - `frontend/src/api/**`
  - `orchestrator/apps/api_v2/views/system.py`
  - `orchestrator/apps/api_v2/views/runtime_settings.py`
  - new `orchestrator/apps/api_v2/views/runtime_control*.py`
  - `orchestrator/apps/core/permission_codes.py`
  - `orchestrator/apps/runtime_settings/{registry.py,effective.py}`
  - `orchestrator/apps/operations/models/**`
  - `go-services/worker/internal/scheduler/**`
  - `go-services/worker/internal/orchestrator/**`
  - `debug/runtime-inventory.sh`
  - `debug/restart-runtime.sh`
  - frontend/backend tests for authz, runtime settings, scheduler controls, and `/system-status`

## Non-Goals
- Открывать generic remote shell, arbitrary command execution или browser-to-host command bridge.
- Вводить новый top-level route вместо `/system-status`.
- Делать visual redesign observability widgets вне control drill-down, необходимого для runtime operations.
- Переписывать pool factual business semantics сверх добавления operator-facing scheduler controls.
- Подменять pool-specific factual workspace refresh глобальным scheduler trigger.
- Завершать полный multi-host/service-manager rollout в том же change; в scope входит contract и local/hybrid-first provider path.

## Assumptions
- `worker-workflows` остаётся owner'ом Go scheduler, а runtime control plane управляет allowlisted runtimes и jobs поверх этого runtime.
- Immediate lifecycle/trigger actions живут в `/system-status`, а declarative scheduler policy остаётся в `/settings/runtime`.
- Первый rollout может стартовать как staff-only local/hybrid control plane с provider abstraction для дальнейшего расширения.
