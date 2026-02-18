# Staging rehearsal plan: refactor-shared-odata-core

## Objective
Подтвердить операционную и контрактную готовность к Big-bang cutover без mixed-mode.

## Test matrix
1. Generic CRUD path (`odataops`):
- create/update/delete/query

2. Publication path (`pool.publication_odata`):
- success
- partial_success
- failed with retry budget

3. Bridge fail-closed:
- explicit call with `operation_type=pool.publication_odata` returns `409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`

4. Read-model compatibility:
- `/api/v2/pools/runs/{run_id}/report` keeps `publication_attempts`, `publication_summary`, `diagnostics`

## Rehearsal steps
1. [ ] Deploy staging candidate builds.
2. [ ] Run contract tests and integration tests.
3. [ ] Execute parity suite and collect diff report.
4. [ ] Run scenario `pool run 500 on 3 organizations`.
5. [ ] Execute rollback drill and verify recovery.

## Evidence to store
- Test logs
- Contract test report
- Parity diff summary
- Rollback drill timestamped results

## Pass criteria
- All rehearsal checks green.
- No contract regressions.
- No unresolved high-severity findings.
