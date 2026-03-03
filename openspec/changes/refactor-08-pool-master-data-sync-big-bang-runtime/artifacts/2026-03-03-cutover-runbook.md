# Cutover Runbook (2026-03-03)

Change: `refactor-08-pool-master-data-sync-big-bang-runtime`

## Canonical runbook

- `docs/observability/POOL_MASTER_DATA_SYNC_BIG_BANG_CUTOVER_RUNBOOK.md`

## Required protocol

1. `freeze`
2. `drain`
3. `watermark capture`
4. `enable`

## Command references

Dry-run:

```bash
cd orchestrator && ./venv/bin/python manage.py run_pool_master_data_sync_cutover --strict --gate-report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-readiness-gate-report.json --report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-cutover-dry-run-report.json
```

Apply:

```bash
cd orchestrator && ./venv/bin/python manage.py run_pool_master_data_sync_cutover --execute-enable --strict --gate-report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-readiness-gate-report.json --report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-cutover-apply-report.json
```
