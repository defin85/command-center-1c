# add-09 follow-up: Requirement -> Code -> Test (2026-03-05)

## pool-master-data-sync

### Requirement: Bootstrap import from IB MUST использовать staged asynchronous job lifecycle
- Status: implemented
- Code:
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_service.py`
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_runtime.py`
- Test:
  - `orchestrator/apps/api_v2/tests/test_intercompany_pool_master_data_bootstrap_api.py::test_bootstrap_jobs_dry_run_execute_list_and_get`
  - `orchestrator/apps/api_v2/tests/test_intercompany_pool_master_data_bootstrap_api.py::test_bootstrap_retry_failed_chunks_keeps_idempotent_effects`

### Requirement: Bootstrap import MUST быть dependency-aware, chunked и идемпотентным
- Status: implemented
- Code:
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_service.py`
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_dependency_order.py`
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_idempotency.py`
- Test:
  - `orchestrator/apps/intercompany_pools/tests/test_master_data_bootstrap_import_dependency_order.py`
  - `orchestrator/apps/intercompany_pools/tests/test_master_data_bootstrap_import_idempotency.py`
  - `orchestrator/apps/api_v2/tests/test_intercompany_pool_master_data_bootstrap_api.py::test_bootstrap_retry_failed_chunks_keeps_idempotent_effects`

### Requirement: Bootstrap import MUST сохранять sync safety инварианты
- Status: implemented
- Code:
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_service.py`
- Test:
  - `orchestrator/apps/api_v2/tests/test_intercompany_pool_master_data_bootstrap_api.py::test_bootstrap_execute_marks_inbound_origin_and_keeps_partial_diagnostics`

## pool-master-data-hub-ui

### Requirement: Pool master-data workspace MUST предоставлять операторский Bootstrap Import from IB wizard
- Status: implemented
- Code:
  - `frontend/src/pages/Pools/masterData/BootstrapImportTab.tsx`
  - `frontend/src/api/intercompanyPools.ts`
- Test:
  - `frontend/src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx::runs bootstrap import preflight, dry-run and execute flow`

### Requirement: UI MUST enforce preflight/dry-run gate before execute
- Status: implemented
- Code:
  - `frontend/src/pages/Pools/masterData/BootstrapImportTab.tsx`
- Test:
  - `frontend/src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx::keeps bootstrap form values after preflight error`

### Requirement: UI MUST показывать прогресс, итог и операторские действия по bootstrap job
- Status: implemented
- Code:
  - `frontend/src/pages/Pools/masterData/BootstrapImportTab.tsx`
  - `frontend/src/api/intercompanyPools.ts`
- Test:
  - `frontend/src/pages/Pools/__tests__/PoolMasterDataPage.test.tsx::runs retry failed chunks action for bootstrap job`

## Follow-up gap closure (this delivery)

- Async execute/retry removed from synchronous request-path; API now enqueues worker execution and returns non-terminal job state.
- Source adapter switched to OData pagination with explicit mapping config (`bootstrap_import_source.entities.*`).
- Metadata rows path is allowed only in explicit mode: `bootstrap_import_source_mode=metadata_rows`.
