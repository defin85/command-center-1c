# 2026-03-29 Live Default-Path Evidence

- Change: `add-pool-factual-balance-monitoring`
- Capture time: `2026-03-29`
- Pool: `5e843d4c-f1d1-4de9-a8c2-594cc7572330` (`top-down-pool-20260325143110`)
- Tenant: `4d29aa0d-3fcc-41b2-878a-28f84f6f75ec`
- Receipt batch: `f46f3eb3-a8e1-4221-8a3b-d6610b7b226d`
- Linked safe run: `7eba14c2-6ad0-4372-b9d8-010aefc27ad1`
- Workflow execution: `a3f70446-4463-4e50-8ecc-a1b34e923571`

## Commands

```bash
ACCESS_TOKEN=$(./venv/bin/python manage.py shell -c "from django.contrib.auth.models import User; from rest_framework_simplejwt.tokens import RefreshToken; user=User.objects.get(username='admin'); print(str(RefreshToken.for_user(user).access_token))" | tail -n 1)

curl --noproxy '*' -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: 4d29aa0d-3fcc-41b2-878a-28f84f6f75ec" \
  "http://localhost:8200/api/v2/pools/runs/7eba14c2-6ad0-4372-b9d8-010aefc27ad1/report/"

curl --noproxy '*' -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CC1C-Tenant-ID: 4d29aa0d-3fcc-41b2-878a-28f84f6f75ec" \
  "http://localhost:8200/api/v2/pools/factual/workspace/?pool_id=5e843d4c-f1d1-4de9-a8c2-594cc7572330&quarter_start=2026-04-01"
```

Note:
- local evidence was captured from the orchestrator HTTP boundary after applying the code change;
- the default frontend/api-gateway path is covered by the shipped API/browser tests and uses the same public payload contract.

## Report Excerpt

```json
{
  "run": {
    "id": "7eba14c2-6ad0-4372-b9d8-010aefc27ad1",
    "status": "published",
    "publication_step_state": "completed",
    "workflow_execution_id": "a3f70446-4463-4e50-8ecc-a1b34e923571",
    "batch_id": "f46f3eb3-a8e1-4221-8a3b-d6610b7b226d"
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
    "quarter_end": "2026-06-30",
    "incoming_amount": "200.00",
    "outgoing_amount": "0.00",
    "open_balance": "200.00",
    "pending_review_total": 0,
    "attention_required_total": 0,
    "backlog_total": 4,
    "freshness_state": "stale",
    "source_availability": "available",
    "last_synced_at": null,
    "settlement_total": 2,
    "checkpoint_total": 4
  },
  "review_queue_summary": {
    "pending_total": 0,
    "unattributed_total": 0,
    "late_correction_total": 0,
    "attention_required_total": 0
  },
  "settlement_count": 2,
  "edge_count": 0
}
```

## Verdict

- The default live path produced a linked published run for the canonical receipt batch.
- The factual workspace exposed explicit `backlog_total` together with `freshness_state=stale`, so read backlog is no longer hidden behind source availability alone.
- The same cohort also passed the published-surfaces preflight gate recorded in `2026-03-29-pilot-preflight-evidence.json`.
