## 1. OpenSpec And Contracts
- [ ] 1.1 Зафиксировать manual launch contract в `pool-master-data-sync` и `pool-master-data-hub-ui`, включая `cluster_all`, `database_set`, launch history/detail и capability-gated entity scope.
- [ ] 1.2 Обновить OpenAPI для новых `/api/v2/pools/master-data/sync-launches/*` endpoint-ов и generated frontend contracts.

## 2. Backend Domain And API
- [ ] 2.1 Добавить persistence для parent launch request и per-scope launch items с immutable snapshot выбранных targets и entity scope.
- [ ] 2.2 Реализовать server-side target resolution для `cluster_all` и `database_set`, fail-closed validation для tenant scope и empty target set.
- [ ] 2.3 Реализовать async fan-out path, который chunked вызывает существующие child sync trigger entrypoint-ы без bypass текущего workflow/runtime path.
- [ ] 2.4 Реализовать coalescing для already-active child scope jobs и machine-readable item outcome для `scheduled`, `coalesced`, `skipped`, `failed`.
- [ ] 2.5 Добавить list/detail/create API для launch history и launch detail, включая aggregate counters и ссылки на child `sync_job_id`.

## 3. Frontend Sync Workspace
- [ ] 3.1 Расширить `/pools/master-data?tab=sync` action bar кнопкой `Launch Sync` и launcher drawer через platform-owned form shell.
- [ ] 3.2 Добавить UI для выбора `mode`, `target_mode`, кластера или набора ИБ и registry-driven entity scope.
- [ ] 3.3 Добавить launch history/detail surface с aggregate counters, per-item outcomes и deep-link handoff в существующий `Sync Status`.
- [ ] 3.4 Перевести target selection на cluster-aware refs вместо текущего `SimpleDatabaseRef`.
- [ ] 3.5 Сохранить fail-closed capability gating: unsupported entities не появляются в launcher options, а API errors не сбрасывают введённый scope.

## 4. Verification
- [ ] 4.1 Добавить pytest coverage на create/list/detail launch API, target snapshot semantics, coalescing и mixed outcome fan-out.
- [ ] 4.2 Добавить frontend unit tests на launcher drawer, target selection, capability gating и launch history/detail rendering.
- [ ] 4.3 Прогнать `./scripts/dev/pytest.sh -q orchestrator/apps/api_v2/tests/test_intercompany_pool_master_data_sync_api.py orchestrator/apps/intercompany_pools/tests/test_master_data_sync_execution.py orchestrator/apps/intercompany_pools/tests/test_master_data_sync_reconcile_scheduler.py <new targeted tests>`.
- [ ] 4.4 Прогнать `cd frontend && npm run generate:api`, `cd frontend && npm run lint`, `cd frontend && npm run test:run -- src/pages/Pools/__tests__/...`.
- [ ] 4.5 Прогнать `openspec validate add-03-pool-master-data-manual-sync-launches --strict --no-interactive`.
