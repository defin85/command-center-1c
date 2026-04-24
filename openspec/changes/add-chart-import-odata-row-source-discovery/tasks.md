## 1. Backend Row-Source Discovery
- [x] 1.1 Extend chart discovery candidate DTO/schema with `row_source_status`, `row_source_kind`, `row_source_entity_name`, `row_source_field_mapping`, `row_source_select_fields`, `row_source_evidence_fingerprint`, and row-source diagnostics.
- [x] 1.2 Derive standard OData row source for `ChartOfAccounts_*` entities with deterministic `Ref_Key`, `Code`, and `Description` mapping.
- [x] 1.3 Add bounded OData row-source probe that validates endpoint/auth/entity/required fields without fetching the full chart.
- [x] 1.4 Mark metadata-only candidates as identity-ready but not initial-load-ready when no readable row source is known.
- [x] 1.5 Preserve fail-closed diagnostics for missing credentials, missing entity, missing fields, ambiguous row source, and tenant mismatch.
- [x] 1.6 Ensure discovery is read-only: it may return row-source proposals/probe evidence but must not create chart sources or mutate `Database.metadata`.
- [x] 1.7 Redact secrets and raw row payloads from discovery responses, diagnostics, provenance, audit trail, and Problem Details.

## 2. Source Persistence and Lifecycle
- [x] 2.1 Extend chart source upsert to accept selected row source provenance from a discovery candidate.
- [x] 2.2 Persist chart-scoped row source metadata without silently mutating global `Database.metadata.bootstrap_import_source`.
- [x] 2.3 Include row source evidence in `source_revision` token and materialize stale-evidence checks.
- [x] 2.4 Update chart preflight to require row-source readiness before dry-run.
- [x] 2.5 Update chart dry-run/materialize row loading to use chart-scoped row source and fall back to existing database mapping only when explicitly compatible.
- [x] 2.6 Snapshot any reused global bootstrap mapping into chart source metadata so post-dry-run global mapping changes cannot silently affect materialize.
- [x] 2.7 Add deterministic paging/fingerprint handling for full row fetch and surface snapshot-consistency diagnostics when stable ordering is unavailable.

## 3. API and Contracts
- [x] 3.1 Update OpenAPI schemas and generated API clients for discovery candidate row-source fields and source upsert payload.
- [x] 3.2 Add Problem Details error codes for row-source-not-ready, row-source-probe-failed, row-source-mapping-incomplete, and row-source-evidence-stale.
- [x] 3.3 Regenerate and verify contract artifacts.

## 4. Frontend UX
- [x] 4.1 Show identity readiness and row-source readiness separately in `Chart Import`.
- [x] 4.2 Disable `Prepare Initial Load` for identity-only candidates and show remediation path.
- [x] 4.3 Show row source mapping preview and probe evidence for load-ready candidates.
- [x] 4.4 Keep manual `chart_identity` override advanced, and require explicit row-source mapping/probe before initial load.
- [x] 4.5 Show stale row-source evidence as "repeat preflight/dry-run" instead of allowing materialize.

## 5. Verification
- [x] 5.1 Add backend tests for `ChartOfAccounts_*` OData row-source derivation and bounded probe.
- [x] 5.2 Add backend tests for metadata-only identity candidate blocked from initial load.
- [x] 5.3 Add backend tests proving row-source mapping/evidence changes reject stale materialize.
- [x] 5.4 Add frontend tests for load-ready candidate, identity-only blocked candidate, and row-source mapping preview.
- [x] 5.5 Add backend tests proving discovery/source provenance does not expose credentials, auth headers, or raw chart rows.
- [x] 5.6 Add backend tests for explicit global mapping compatibility and snapshot behavior.
- [x] 5.7 Run focused backend chart import tests.
- [x] 5.8 Run frontend `PoolMasterDataPage.chartImport` tests.
- [x] 5.9 Run contract validation/generation checks.
- [x] 5.10 Run `openspec validate add-chart-import-odata-row-source-discovery --strict --no-interactive`.
