# 2026-04-05 Live Cutover And Rollback Evidence

- Change: `03-bridge-pool-factual-scope-to-gl-account-set`
- Capture time: `2026-04-05`
- Pool: `5e843d4c-f1d1-4de9-a8c2-594cc7572330` (`top-down-pool-20260325143110`)
- Tenant: `4d29aa0d-3fcc-41b2-878a-28f84f6f75ec`
- Database: `4e67a533-729d-4512-a7ae-e3460d46f276` (`dom_lesa_7726446503`)
- Quarter: `2026-04-01 .. 2026-06-30`
- Selector key: `pool:5e843d4c-f1d1-4de9-a8c2-594cc7572330:sales_report_v1:2026-04-01`
- GLAccountSet: `810fd944-053e-46fa-8f36-b24a90796c3f`
- Revision: `gl_account_set_rev_630d261f938748618f747f75a75ee9cd`
- Scope fingerprint: `1dfe3996f65342bc3d69239ea33c733b996cbf18c962739abb0721adce70ce67`

## Commands

```bash
cd orchestrator && ./venv/bin/python manage.py preflight_pool_factual_sync \
  --pool-id 5e843d4c-f1d1-4de9-a8c2-594cc7572330 \
  --quarter-start 2026-04-01 \
  --requested-by-username admin \
  --database-id 4e67a533-729d-4512-a7ae-e3460d46f276 \
  --json \
  --strict

./debug/eval-django.sh "from apps.intercompany_pools.master_data_bindings import upsert_pool_master_data_binding; ..."

./debug/eval-django.sh "from apps.intercompany_pools.factual_workspace_runtime import _get_or_create_checkpoint_for_scope, _update_checkpoint_scope_contract, resolve_pool_factual_scope; ..."
```

## Observed Sequence

1. Initial live preflight returned `decision=no_go` with `POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_MISSING` for canonical members `factual_sales_report_62_01` and `factual_sales_report_90_01`.
2. Live chart-of-accounts lookup for `ChartOfAccounts_Хозрасчетный` on `dom_lesa_7726446503` resolved:
   - `62.01 -> 020635d6-54e8-11e9-80ee-0050569f2e9f`
   - `90.01 -> 02063682-54e8-11e9-80ee-0050569f2e9f`
3. Missing bindings were materialized through the checked-in master-data binding store path `upsert_pool_master_data_binding(...)`, not direct SQL:
   - `factual_sales_report_62_01 -> d9a06774-7446-4dba-8b0d-5e9483211f98`
   - `factual_sales_report_90_01 -> 69cb5479-031e-4cca-b562-62ae98c46da6`
4. Re-running live preflight after the binding backfill returned `decision=go`.
5. The resulting factual scope contract now carries pinned `resolved_bindings` from the binding table with matching live codes.
6. A historical `PoolFactualSyncCheckpoint` for the same pool/database/quarter was updated through the runtime workspace compatibility path from legacy empty `scope_fingerprint` to the new selector-based fingerprint, and its metadata received `factual_scope_contract.v2` with pinned `resolved_bindings`.

## Preflight Before Binding Backfill

```json
{
  "decision": "no_go",
  "checks": {
    "gl_account_bindings": {
      "ok": false,
      "code": "POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_MISSING"
    },
    "live_probe": {
      "ok": false,
      "detail": "GLAccountSet binding coverage did not succeed"
    }
  }
}
```

## Preflight After Binding Backfill

```json
{
  "decision": "go",
  "checks": {
    "gl_account_bindings": {
      "ok": true,
      "detail": "selected GLAccountSet coverage resolved and pinned for the target database"
    },
    "bounded_scope": {
      "ok": true
    },
    "live_probe": {
      "ok": true,
      "detail": "live bounded factual reads completed successfully"
    }
  }
}
```

## Resolved Bindings

```json
[
  {
    "canonical_id": "factual_sales_report_62_01",
    "code": "62.01",
    "target_ref_key": "020635d6-54e8-11e9-80ee-0050569f2e9f",
    "binding_source": "binding_table",
    "live_code": "62.01"
  },
  {
    "canonical_id": "factual_sales_report_90_01",
    "code": "90.01",
    "target_ref_key": "02063682-54e8-11e9-80ee-0050569f2e9f",
    "binding_source": "binding_table",
    "live_code": "90.01"
  }
]
```

## Historical Checkpoint Compatibility

- Checkpoint: `3b0adf39-7d48-4305-816c-c2de9b4318f7`
- Before compatibility pass:
  - top-level `scope_fingerprint = ""`
  - metadata contained only legacy `source_scope` payload
- After compatibility pass through `_get_or_create_checkpoint_for_scope(...)` + `_update_checkpoint_scope_contract(...)`:
  - top-level `scope_fingerprint = 1dfe3996f65342bc3d69239ea33c733b996cbf18c962739abb0721adce70ce67`
  - metadata includes `factual_scope_contract.v2`
  - metadata includes pinned `resolved_bindings`
  - no rebuild of the historical checkpoint row was required

## Verdict

- Live cutover gate is green for the pilot contour: selected `GLAccountSet` coverage is now materialized and verified against live OData.
- The new selector-based factual scope contract is pinned into readiness metadata and live preflight output.
- Historical checkpoint compatibility remains rollback-safe: an existing legacy checkpoint can be adopted into the new `scope_fingerprint` and `factual_scope_contract.v2` path without rebuilding the checkpoint record.
