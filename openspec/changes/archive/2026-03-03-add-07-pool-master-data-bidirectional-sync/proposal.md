# Change: Двусторонняя синхронизация master-data между CC и 1С ИБ

## Why
`add-05-cc-master-data-hub` и `add-06-pool-master-data-hub-ui` ввели канонический master-data слой, bindings и операторский UI, но не ввели постоянную двустороннюю синхронизацию между CC и целевыми ИБ.

Сейчас данные могут дрейфовать:
- изменения в CC не гарантированно доходят до ИБ в фоновом режиме;
- изменения в ИБ не попадают обратно в CC автоматически;
- отсутствует формализованный контракт конфликтов и checkpoint/replay semantics.

## What Changes
- Ввести новую capability `pool-master-data-sync` для двусторонней синхронизации `CC <-> ИБ`.
- Зафиксировать два синхронизационных контура:
  - outbound `CC -> ИБ` через transactional outbox и идемпотентный dispatcher;
  - inbound `ИБ -> CC` через exchange-plan polling (`SelectChanges`/`NotifyChangesReceived`) и checkpoint.
- Зафиксировать обязательный orchestration path для долгих sync-операций:
  - `domain master-data sync -> workflows -> operations -> redis worker -> OData/exchange-plan transport`.
- Зафиксировать fail-closed правило: long-running sync НЕ выполняется синхронно в API-request.
- Ввести policy источника истины на scope сущности (`cc_master`, `ib_master`, `bidirectional`) и fail-closed правила обработки конфликтов.
- Ввести единый контракт anti-loop (`origin_system`, `origin_event_id`) и дедупликации для at-least-once доставки.
- Ввести операторский read-model синхронизации: lag, retries, checkpoints, conflict queue, manual retry/reconcile.
- Расширить runtime settings override ключами управления sync-контуром и policy по tenant.
- Зафиксировать persistence boundary: `sync_job/sync_scope/sync_checkpoint/sync_outbox/sync_conflict` хранятся в общем Postgres (текущая БД), отдельными таблицами домена sync, без выделения отдельной физической БД.

## Impact
- Affected specs:
  - `pool-master-data-sync` (new)
  - `runtime-settings-overrides`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/**` (sync domain, checkpoints, conflicts, reconcile)
  - `orchestrator/apps/api_v2/views/workflows/**` (workflow orchestration entrypoints)
  - `orchestrator/apps/operations/**` (operations root projection, enqueue/outbox, stream integration)
  - `orchestrator/apps/api_v2/views/intercompany_pools*` (sync status/reconcile API)
  - `orchestrator/apps/runtime_settings/**` (sync keys and resolver wiring)
  - `go-services/worker/internal/**` (worker handlers for sync workflow steps and OData/exchange-plan calls)
  - `frontend/src/pages/Pools/**` (sync status/conflicts UX)
  - `frontend/src/api/intercompanyPools.ts`
  - `contracts/orchestrator/**` (new API contract surfaces)

## Non-Goals
- Не реализовывать в этом change полную миграцию исторических данных из всех ИБ.
- Не добавлять fuzzy matching/ML-сопоставление master-data.
- Не менять бизнес-алгоритмы распределения сумм в pool run.
- Не менять существующий fail-closed контракт `master_data_gate` в публикации, кроме интеграции с sync read-model.

## Dependencies
- Change зависит от `add-05-cc-master-data-hub` (canonical entities + bindings + gate).
- Change зависит от `add-06-pool-master-data-hub-ui` (операторские surfaces для master-data).
