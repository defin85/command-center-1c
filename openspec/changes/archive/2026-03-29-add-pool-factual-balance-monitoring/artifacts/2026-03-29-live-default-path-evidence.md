# 2026-03-29 Live Default-Path Evidence

- Change: `add-pool-factual-balance-monitoring`
- Capture time: `2026-03-29`
- Pool: `5e843d4c-f1d1-4de9-a8c2-594cc7572330` (`top-down-pool-20260325143110`)
- Tenant: `4d29aa0d-3fcc-41b2-878a-28f84f6f75ec`
- Receipt batch: `5e4d8b43-04d7-44f2-a58e-a00902b5f4dc`
- Linked safe run: `319e95ff-04b3-46d3-aca6-8ae0a685d075`
- Workflow execution: `0379a6c6-299c-4da0-a919-bacc0faa7a24`
- Quarter: `2026-04-01 .. 2026-06-30`

## Public-path commands

```bash
ACCESS_TOKEN=$(./venv/bin/python manage.py shell -c "from django.contrib.auth.models import User; from rest_framework_simplejwt.tokens import RefreshToken; user=User.objects.get(username='admin'); print(str(RefreshToken.for_user(user).access_token))" | tail -n 1)

curl --noproxy '*' -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: 4d29aa0d-3fcc-41b2-878a-28f84f6f75ec" \
  "http://localhost:8180/api/v2/pools/runs/319e95ff-04b3-46d3-aca6-8ae0a685d075/report/"

curl --noproxy '*' -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: 4d29aa0d-3fcc-41b2-878a-28f84f6f75ec" \
  "http://localhost:8180/api/v2/pools/factual/workspace/?pool_id=5e843d4c-f1d1-4de9-a8c2-594cc7572330&quarter_start=2026-04-01"

curl --noproxy '*' -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: 4d29aa0d-3fcc-41b2-878a-28f84f6f75ec" \
  "http://localhost:15173/api/v2/pools/factual/workspace/?pool_id=5e843d4c-f1d1-4de9-a8c2-594cc7572330&quarter_start=2026-04-01"
```

## Observed sequence

1. Public receipt batch create on `8180` produced canonical `PoolBatch` `5e4d8b43-04d7-44f2-a58e-a00902b5f4dc` and linked safe run `319e95ff-04b3-46d3-aca6-8ae0a685d075`.
2. Early `confirm_publication` retry during `approval_state=preparing` returned the expected retryable pre-publish conflict (`AWAITING_PRE_PUBLISH`), not a deadlock.
3. Re-running `confirm_publication` after the run reached `awaiting_approval` was accepted, and the same run converged to `status=published`, `publication_step_state=completed`, `workflow_status=completed`.
4. The factual workspace was reachable through both shipped public entry points: `8180` (gateway) and `15173` (frontend dev proxy).
5. The freshest factual checkpoints no longer fail with `POOL_FACTUAL_SYNC_PAYLOAD_INVALID: document_entities must not be empty`; the newest failures progressed to deeper OData/domain validation (`chart of accounts is missing factual account codes: 62.01, 90.01`), which is evidence that the payload-loss bug was closed.

## Receipt Create Excerpt

```json
{
  "batch": {
    "id": "5e4d8b43-04d7-44f2-a58e-a00902b5f4dc",
    "batch_kind": "receipt",
    "pool_id": "5e843d4c-f1d1-4de9-a8c2-594cc7572330",
    "start_organization_id": "51b8fa3d-1d90-45a0-8621-0dc9e40e49ec",
    "period_start": "2026-04-01",
    "period_end": "2026-06-30"
  },
  "settlement": {
    "id": "56d0b740-b001-4b10-92f2-23701959f5bd",
    "batch_id": "5e4d8b43-04d7-44f2-a58e-a00902b5f4dc",
    "status": "ingested",
    "incoming_amount": "100.00",
    "open_balance": "100.00"
  },
  "run": {
    "id": "319e95ff-04b3-46d3-aca6-8ae0a685d075",
    "status": "validated",
    "approval_state": "preparing",
    "publication_step_state": "not_enqueued",
    "workflow_status": "pending"
  }
}
```

## Published Report Excerpt

```json
{
  "run": {
    "id": "319e95ff-04b3-46d3-aca6-8ae0a685d075",
    "status": "published",
    "approval_state": "approved",
    "publication_step_state": "completed",
    "workflow_status": "completed",
    "publication_confirmed_at": "2026-03-29T19:30:43.468374Z",
    "publishing_started_at": "2026-03-29T19:30:51.406940Z",
    "completed_at": "2026-03-29T19:30:51.416721Z"
  },
  "publication_summary": {
    "max_attempts": 5,
    "total_targets": 4,
    "failed_targets": 0,
    "succeeded_targets": 4
  },
  "attempts_by_status": {
    "success": 10
  }
}
```

## Factual Workspace Excerpt

```json
{
  "summary": {
    "quarter": "2026Q2",
    "quarter_start": "2026-04-01",
    "incoming_amount": "500.00",
    "outgoing_amount": "0.00",
    "open_balance": "500.00",
    "backlog_total": 4,
    "freshness_state": "stale",
    "source_availability": "available",
    "last_synced_at": null,
    "settlement_total": 5,
    "checkpoint_total": 4
  },
  "review_queue": {
    "contract_version": "pool_factual_review_queue.v1",
    "subsystem": "reconcile_review",
    "summary": {
      "pending_total": 0,
      "unattributed_total": 0,
      "late_correction_total": 0,
      "attention_required_total": 0
    }
  }
}
```

## Post-review checkpoint excerpt

```json
[
  {
    "id": "03cae846-ef69-4a48-ad98-bea7ec32a93d",
    "lane": "read",
    "workflow_status": "failed",
    "last_error_code": "POOL_FACTUAL_SYNC_FAILED",
    "last_error": "POOL_FACTUAL_SYNC_ODATA_FAILED: [execution_error] node execution failed (node: factual_sync_source_slice): POOL_FACTUAL_SYNC_ODATA_FAILED: chart_of_accounts: chart of accounts is missing factual account codes: 62.01, 90.01"
  }
]
```

## Dev-automation coverage completing scenario 5.3

- `receipt batch -> linked run context` is covered by the public live capture above and the operator regression in `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx`.
- `sale batch/manual sale capture` is covered by `frontend/tests/browser/pools-full-flow-ui.spec.ts` and `orchestrator/apps/intercompany_pools/tests/test_sale_batch_intake.py`.
- `refreshed summary -> manual reconcile late correction` is covered by `orchestrator/apps/api_v2/tests/test_pool_factual_api.py` and `frontend/src/pages/Pools/__tests__/PoolFactualPage.test.tsx`.
- `quarter_start` handoff from `/pools/runs` to `/pools/factual` is covered by `frontend/tests/browser/ui-platform-contract.spec.ts`.

## Verdict

- The default public path now proves `receipt batch -> linked run -> confirm publication -> published report -> factual workspace` without requiring a private helper path.
- The pilot/preflight cohort still passes the bounded published-surfaces gate recorded in `2026-03-29-pilot-preflight-evidence.json`, and that bundle now includes explicit `boundary_probes.*.probe_ok=true` evidence.
- The full `5.3` acceptance trail is satisfied by combining the live public receipt/report/workspace capture with checked-in browser/backend automation for sale intake, refreshed factual summary and manual reconcile review flows.
