## 1. Backend Discovery Contract
- [x] 1.1 Add chart candidate discovery service for a selected database.
- [x] 1.2 Support derivation from OData chart entity names, metadata catalog chart-typed fields, explicit source mapping metadata, and metadata rows.
- [x] 1.3 Include metadata/source evidence fingerprints in candidate payloads and avoid full chart row fetch as the default discovery mechanism.
- [x] 1.4 Return candidate diagnostics when identity cannot be derived fail-closed.
- [x] 1.5 Add tenant/auth-bounded API endpoint and OpenAPI schemas for chart discovery.

## 2. Source Setup and Initial Load
- [x] 2.1 Extend authoritative source upsert to accept discovered candidate provenance.
- [x] 2.2 Extend source row mapping so chart config can stamp `chart_identity` when the OData entity itself is `ChartOfAccounts_*`.
- [x] 2.3 Add guided initial-load orchestration or UI-side composition for source upsert plus `preflight -> dry-run -> materialize`.
- [x] 2.4 Require auditable operator review of dry-run counters before materialize.
- [x] 2.5 Invalidate or reject stale materialize attempts when source revision/discovery evidence changed after dry-run.
- [x] 2.6 Audit manual `chart_identity` override with reason and discovery diagnostics.

## 3. Frontend UX
- [x] 3.1 Replace primary free-text `chart_identity` setup with reference database selection plus discovered chart selector.
- [x] 3.2 Add initial-load action from selected reference database and chart candidate.
- [x] 3.3 Show candidate derivation/confidence and incomplete-candidate diagnostics.
- [x] 3.4 Keep manual override as advanced/fail-closed path, not the default setup.

## 4. Verification
- [x] 4.1 Add backend tests for discovery from OData config, metadata catalog snapshot, metadata rows, incomplete mapping, and manual override audit.
- [x] 4.2 Add backend API tests for discovery auth/tenant boundaries and initial-load lifecycle gating.
- [x] 4.3 Add backend tests proving stale source/discovery evidence cannot authorize materialize.
- [x] 4.4 Add frontend tests for discovered chart selection and initial-load flow.
- [x] 4.5 Run `openspec validate add-chart-import-discovery-and-initial-load --strict --no-interactive`.
- [x] 4.6 Run focused backend chart import tests and frontend `PoolMasterDataPage.chartImport` tests.
