# Change: Перестройка frontend query/stream runtime для устойчивого default path

## Why
После `refactor-ui-platform-on-ant` проблемный участок стал виден на default operator path: `/decisions` и `/pools/binding-profiles` под staff-сессией регулярно получают `429 Too Many Requests`, а UI засыпает пользователя повторяющимися ошибками.

Текущая причина не в одной странице и не в одном endpoint, а в связке архитектурных anti-pattern:
- один глобальный React Query policy применяет одинаковые `retry`/`refetchOnWindowFocus` ко всем типам данных;
- app shell поднимает несколько capability/bootstrap probe-запросов параллельно;
- database SSE stream управляется singleton-ом, который одновременно владеет transport, cache invalidation, reconnect и UX ошибок;
- stream ticket по умолчанию запрашивается с `force=true`, что делает takeover штатным путём;
- открытие/переподключение stream само по себе инвалидирует query cache;
- тяжёлые secondary reads (`organization pools`, decisions bootstrap path) стартуют eager на mount.

Локальные page-фиски тут недостаточны. Нужен отдельный change, который зафиксирует правильную архитектуру runtime-слоя, а не ещё один набор ad-hoc флагов.

## What Changes
- Добавить новую capability `ui-realtime-query-runtime`.
- Добавить новую capability `database-realtime-streaming`.
- Зафиксировать workload-aware query policy registry вместо одного глобального набора retry/refetch defaults.
- Зафиксировать единый shell/bootstrap contract вместо capability probe-запросов как primary path.
- Зафиксировать browser-scoped realtime coordination: один stream owner на браузер, followers получают события через cross-tab coordination.
- Зафиксировать, что database stream invalidation является event-driven и scoped по query keys, а не blanket invalidation при `onOpen`.
- Зафиксировать conservative stream ownership contract: default connect без silent takeover, явный recovery path только по operator/developer action.
- Зафиксировать request-budget правила для `/decisions` и `/pools/binding-profiles`, чтобы heavy secondary reads не стартовали без необходимости.
- Зафиксировать dedupe/error-classification policy для repeated background `429` и transport errors.

## Impact
- Affected specs:
  - `ui-realtime-query-runtime` (new)
  - `database-realtime-streaming` (new)
- Related existing specs:
  - `ui-frontend-performance`
  - `pool-binding-profiles`
  - `database-metadata-management-ui`
- Affected code (expected, when implementing this change):
  - `frontend/src/lib/queryClient.ts`
  - `frontend/src/api/client.ts`
  - `frontend/src/api/sse.ts`
  - `frontend/src/stores/databaseStreamManager.ts` or replacement modules
  - `frontend/src/contexts/DatabaseStreamContext.tsx`
  - `frontend/src/hooks/useDatabaseStreamInvalidation.ts`
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/authz/AuthzProvider.tsx`
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`
  - `frontend/tests/browser/**`
  - `orchestrator/apps/api_v2/views/databases/streaming.py`
  - `contracts/api-gateway/**`
  - docs/runbook files for frontend runtime validation

## Non-Goals
- Точечный hotfix только для `/decisions` без исправления общего runtime anti-pattern.
- Big-bang rewrite всех frontend data hooks за один шаг.
- Замена SSE на другой transport (`WebSocket`, polling-only) без отдельного architectural change.
- Ослабление gateway rate limit как primary solution.
- Маскировка repeated `429` только UI-notification suppression без изменения transport/query ownership model.

## Assumptions
- Database SSE остаётся canonical realtime source для database-related invalidation.
- Для одного browser instance допустим один active database stream owner с follower tabs через cross-tab coordination.
- Для разных browser/client instances одного пользователя система должна поддерживать детерминированный session/lease contract без silent eviction по умолчанию.
- Query freshness для admin routes должна в первую очередь обеспечиваться event-driven invalidation и explicit refresh actions, а не агрессивным focus/reconnect refetch.
