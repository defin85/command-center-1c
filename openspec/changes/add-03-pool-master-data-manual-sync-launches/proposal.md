# Change: Добавить manual sync launches для pool master-data workspace

## Why
Текущий `/pools/master-data?tab=sync` уже показывает operator-facing read-model синхронизации и conflict remediation, но не даёт явного способа вручную запустить сбор или синхронизацию данных по целевому набору ИБ. В результате оператор может только ждать фоновые триггеры после `upsert`/conflict action или использовать отдельные служебные entrypoint-ы вне UI.

Для реальной операционной работы этого недостаточно. Пользователю нужен контролируемый ручной запуск:
- по всем ИБ выбранного кластера;
- по явному набору конкретных ИБ;
- в одном из режимов `inbound`, `outbound` или `reconcile`;
- с прозрачным результатом fan-out по каждому `(database, entity)` scope.

При этом существующий runtime уже умеет исполнять sync только в per-database scope `(tenant, database, entity)` и уже имеет workflow-backed child trigger path, policy gates, affinity resolution и conflict queue. Поэтому change должен добавлять operator launcher поверх этих shipped boundaries, а не вводить второй parallel sync runtime.

## What Changes
- Расширить `Sync` зону в `/pools/master-data` явным operator action `Launch Sync`.
- Поддержать manual launch modes:
  - `inbound` (`ИБ -> CC`, сбор изменений из ИБ);
  - `outbound` (`CC -> ИБ`, публикация canonical изменений);
  - `reconcile` (ручной fan-out сверки).
- Поддержать два target mode:
  - `cluster_all` — все ИБ выбранного кластера в immutable snapshot на момент принятия запроса;
  - `database_set` — явный список выбранных ИБ.
- Добавить parent launch request и per-scope launch items как operator-facing read-model:
  - immutable snapshot выбранных целей и entity scope;
  - aggregate counters `scheduled/coalesced/skipped/failed/completed`;
  - детализацию по child scope и ссылки на созданные/переиспользованные sync jobs.
- Выполнять fan-out асинхронно и chunked, с переиспользованием существующих child trigger функций и существующего workflow path для per-database sync jobs.
- При наличии уже активного `(tenant, database, entity, direction)` scope не создавать duplicate child job, а коалесцировать запуск в существующий активный sync job с явным operator-facing статусом.
- Оставить capability, policy, affinity и fail-closed semantics на child scope уровне; parent launcher не должен переписывать эти правила.
- Добавить в UI launch history/detail surface и deep-link handoff в существующий `Sync Status`.
- Использовать cluster-aware target refs в UI; не полагаться на текущий `SimpleDatabaseRef`, который не содержит `cluster_id`.

## Impact
- Affected specs:
  - `pool-master-data-sync`
  - `pool-master-data-hub-ui`
- Affected code:
  - `frontend/src/pages/Pools/masterData/SyncStatusTab.tsx`
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/api/queries/rbac/refs.ts`
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data_sync.py`
  - `contracts/**`
- Affected runtime boundaries:
  - `frontend -> api-gateway -> orchestrator -> worker-workflows/worker -> 1C`
  - новые ручные launch request не должны вводить второй primary runtime вне текущего pool sync path

## Non-Goals
- Массовый bootstrap import по кластеру или по набору ИБ.
- Изменение shipped semantics для child `PoolMasterDataSyncJob`.
- Добавление generic sync capabilities для `GLAccount` или `GLAccountSet`.
- Поддержка target mode `all databases across tenant` в одном действии.
- Редактирование scheduling priority, deadline или server affinity из UI в `V1`.
- Полноценный `cancel` для уже запущенного manual launch batch в `V1`.

## Assumptions
- Под "кластером" понимается `databases.Cluster`, связанный с `Database.cluster`.
- Operator launcher остаётся tenant-scoped mutating action и использует тот же fail-closed access class, что и текущие mutating sync actions в master-data workspace.
- Immutable target snapshot фиксируется в момент принятия launch request; дальнейшие изменения cluster membership или списка доступных ИБ не переписывают уже созданный launch.
