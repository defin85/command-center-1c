# Change: Изоляция request budget в API Gateway

## Why
Сейчас `api-gateway` применяет один coarse rate-limit `100 req/min` почти ко всему `/api/v2` трафику на ключе пользователя. В результате тяжёлый background surface или несколько одновременных browser sessions одного staff-пользователя могут выбить `429` не только для собственного route, но и для unrelated shell/control traffic вроде `/api/v2/system/bootstrap/`.

Недавний fix на frontend уже убрал blind retry для UI incident telemetry, но это уменьшает amplification, а не закрывает root cause. Остаточный риск остаётся cross-surface и cross-session: background-heavy route продолжает делить один budget с shell bootstrap и interactive actions.

## What Changes
- Добавить новую capability `api-gateway-request-budget-isolation`.
- Зафиксировать class-aware request budgets в gateway вместо одного undifferentiated per-user bucket.
- Зафиксировать explicit route-to-budget classification для `/api/v2` traffic с bounded default path.
- Зафиксировать machine-readable `429` contract с budget metadata.
- Дополнить `ui-realtime-query-runtime` требованием, что shell/bootstrap и heavy background routes не должны starving'ить друг друга как normal behavior.

## Impact
- Affected specs:
  - `api-gateway-request-budget-isolation` (new)
  - `ui-realtime-query-runtime`
- Affected code:
  - `go-services/api-gateway/internal/routes/router.go`
  - `go-services/api-gateway/internal/routes/orchestrator_routes.go`
  - `go-services/api-gateway/internal/middleware/ratelimit.go`
  - `go-services/shared/config/config.go`
  - `frontend/src/lib/queryRuntime.ts`
  - `frontend/src/observability/uiIncidentTelemetry.ts`
  - `frontend/src/pages/Pools/masterData/SyncStatusTab.tsx`
- Affected verification:
  - `cd go-services/api-gateway && go test ./...`
  - targeted frontend `vitest`
  - browser smoke на shared-session starvation scenario

## Non-Goals
- Простое повышение глобального `100 req/min` как primary solution.
- Unlimited exemption для `/api/v2/system/bootstrap/` или `/api/v2/ui/incident-telemetry/ingest/` без budget isolation.
- Замена существующего stream/session contract в `database-realtime-streaming`.
- Big-bang переписывание всех heavy routes за один rollout.
