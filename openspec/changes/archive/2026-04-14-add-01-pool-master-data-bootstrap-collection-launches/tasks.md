## 1. OpenSpec And Contracts
- [x] 1.1 Зафиксировать batch collection contract для `Bootstrap Import` в `pool-master-data-sync` и `pool-master-data-hub-ui`, включая `cluster_all`, `database_set`, parent history/detail и staged aggregate lifecycle.
- [x] 1.2 Обновить OpenAPI для новых `/api/v2/pools/master-data/bootstrap-collections/*` endpoint-ов и generated frontend contracts.

## 2. Backend Domain And API
- [x] 2.1 Добавить persistence для parent batch collection request и per-database collection items с immutable target snapshot и `entity_scope`.
- [x] 2.2 Реализовать server-side target resolution для `cluster_all` и `database_set`, fail-closed validation для tenant scope и empty target set.
- [x] 2.3 Реализовать staged aggregate orchestration `preflight -> dry_run -> execute -> finalize` поверх существующих per-database bootstrap jobs.
- [x] 2.4 Реализовать coalescing и machine-readable item outcome для случаев, когда child bootstrap job уже активен или когда отдельная база даёт fail-closed diagnostics.
- [x] 2.5 Добавить list/detail/create API для batch collection history и detail, включая aggregate counters и ссылки на child bootstrap jobs.

## 3. Frontend Bootstrap Workspace
- [x] 3.1 Расширить `/pools/master-data?tab=bootstrap-import` batch launcher'ом для `cluster_all` и `database_set`.
- [x] 3.2 Добавить UI для выбора target mode, кластера или набора ИБ и `entity_scope` без потери existing single-database bootstrap flow.
- [x] 3.3 Добавить batch collection history/detail с aggregate progress, per-database outcomes и ссылками на child jobs.
- [x] 3.4 Перевести batch target selection на cluster-aware refs вместо текущего `SimpleDatabaseRef`.
- [x] 3.5 Сохранить fail-closed UX: ошибки create/preflight/dry-run не очищают already selected scope.

## 4. Verification
- [x] 4.1 Добавить pytest coverage на create/list/detail batch collection API, target snapshot semantics, staged aggregation и coalescing.
- [x] 4.2 Добавить frontend unit tests на batch launcher, target selection, staged progress и batch detail rendering.
- [x] 4.3 Прогнать `./scripts/dev/pytest.sh -q <new targeted bootstrap collection tests> orchestrator/apps/api_v2/tests/test_intercompany_pool_master_data_bootstrap_api.py`.
- [x] 4.4 Прогнать `cd frontend && npm run generate:api`, `cd frontend && npm run lint`, `cd frontend && npm run test:run -- src/pages/Pools/__tests__/...`.
- [x] 4.5 Прогнать `openspec validate add-01-pool-master-data-bootstrap-collection-launches --strict --no-interactive`.
