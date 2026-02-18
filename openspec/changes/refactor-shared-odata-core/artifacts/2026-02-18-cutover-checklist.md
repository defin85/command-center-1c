# Cutover checklist: refactor-shared-odata-core

## Scope
Атомарное переключение в одном релизном окне:
- `odataops` -> worker `odata-core`
- `pool.publication_odata` -> worker `odata-core`
- bridge path для `pool.publication_odata` -> fail-closed reject

## Pre-cutover gates (all required)
- [ ] `openspec validate refactor-shared-odata-core --strict --no-interactive`
- [ ] Contract tests green: bridge `409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`
- [ ] Parity suite green: CRUD + publication diagnostics/idempotency/status projection
- [ ] Compatibility preflight green (`odata-compatibility-profile`)
- [ ] Staging rehearsal green
- [ ] Rollback drill green
- [ ] Alert thresholds and abort criteria loaded in monitoring

## Release window controls
- [ ] Release freeze window approved
- [ ] On-call roster confirmed (worker/orchestrator/platform)
- [ ] Incident channel prepared
- [ ] Read-only access to required dashboards and logs verified

## Cutover execution order
1. [ ] Deploy worker release with `odata-core` enabled for `odataops` and publication path.
2. [ ] Deploy orchestrator release with bridge publication fail-closed behavior.
3. [ ] Apply runtime/config guards preventing legacy publication fallback.
4. [ ] Run post-deploy smoke checks:
   - [ ] `POST /api/v2/internal/workflows/execute-pool-runtime-step` with `operation_type=pool.publication_odata` -> `409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`
   - [ ] `GET /api/v2/pools/runs/{run_id}/report` returns compatible `publication_attempts` payload
   - [ ] Generic CRUD through `odataops` works

## Soak window
- [ ] Observe telemetry during agreed soak window
- [ ] No sustained SLO degradation
- [ ] No unexpected growth in retry/error classes

## Exit criteria
- [ ] All smoke checks passed
- [ ] No open Sev-1/Sev-2 incidents related to cutover
- [ ] Rollback not required; release marked stable
