# Change: Добавить multi-database bootstrap collection launches для pool master-data

## Why
Текущий `Bootstrap Import` уже позволяет первично загрузить canonical master-data из одной ИБ через staged lifecycle `preflight -> dry_run -> execute -> finalize`. Но этого недостаточно для целевого operator сценария, в котором пользователь должен собрать reference layer не из одной базы, а по всему выбранному набору ИБ.

Если оператору приходится поочерёдно запускать однобазовый bootstrap вручную десятки раз, система:
- не даёт единого snapshot выбранных целей;
- не даёт aggregate preview по cluster-wide collection;
- не даёт batch-level наблюдаемость по общему сбору reference layer;
- повышает риск неполного покрытия и ручных ошибок.

При этом shipped bootstrap import уже содержит нужные child semantics для одной базы: preflight gating, dry-run summary, chunked execute, retry failed chunks, idempotent upsert и inbound-origin safety. Поэтому change должен поднимать именно operator batch launcher над существующими per-database bootstrap jobs, а не заменять их новой import semantics.

## What Changes
- Расширить `Bootstrap Import` зону в `/pools/master-data` operator action для multi-database collection launches.
- Поддержать target mode:
  - `cluster_all` — все ИБ выбранного кластера в immutable snapshot;
  - `database_set` — явный список выбранных ИБ.
- Сохранить staged lifecycle и на batch уровне:
  - `preflight`;
  - `dry_run`;
  - `execute`;
  - `finalize`.
- Добавить parent collection request и per-database collection items:
  - immutable snapshot выбранных `database_ids` и `entity_scope`;
  - aggregate child outcomes и batch-level progress;
  - ссылки на child per-database bootstrap jobs.
- Выполнять child fan-out асинхронно и chunked, переиспользуя существующий per-database bootstrap job path и его fail-closed diagnostics.
- Поддержать coalescing/explicit outcome, если для конкретной ИБ уже идёт совместимый bootstrap import job.
- Добавить launch history/detail в UI для batch-level collection и handoff в child bootstrap jobs.
- Не менять существующий смысл single-database bootstrap; multi-database collection становится дополнительным operator path поверх него.

## Impact
- Affected specs:
  - `pool-master-data-sync`
  - `pool-master-data-hub-ui`
- Affected code:
  - `frontend/src/pages/Pools/masterData/BootstrapImportTab.tsx`
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/api/queries/rbac/refs.ts`
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data.py`
  - `contracts/**`
- Related changes:
  - complements `add-03-pool-master-data-manual-sync-launches`, which covers cluster/database-scoped rollout and manual sync fan-out from CC to target ИБ / runtime sync paths

## Non-Goals
- Изобретение нового cross-infobase merge algorithm вне существующего canonical resolve+upsert path.
- Замена текущего single-database bootstrap import wizard.
- Автоматический rollout reference layer обратно в ИБ в рамках этого change.
- Tenant-global mode `all databases across tenant` в одном действии.
- Полноценный parent-level `cancel/reprioritize` в `V1`.

## Assumptions
- Multi-database collection orchestrирует уже существующие per-database bootstrap jobs и не подменяет их domain semantics.
- Cross-infobase canonical dedupe и binding behavior по-прежнему определяются существующим canonical resolve+upsert path; новый change не вводит implicit global merge heuristics.
- Immutable target snapshot фиксируется в момент принятия batch request и не меняется после этого.
