# Rollback Protocol (2026-03-03)

Change: `refactor-08-pool-master-data-sync-big-bang-runtime`

## Scope

Rollback для in-flight сообщений после big-bang enablement с сохранением replay-safe semantics.

## Trigger criteria

- gate-breaking инцидент после cutover;
- нарушение checkpoint/ack инвариантов;
- security leak в diagnostics/last_error.

## Procedure

1. Freeze runtime:

```bash
cd orchestrator && ./venv/bin/python manage.py shell -c "from apps.runtime_settings.models import RuntimeSetting; RuntimeSetting.objects.update_or_create(key='pools.master_data.sync.enabled', defaults={'value': False}); print('sync.enabled=false')"
```

2. Capture watermark and drain snapshot:

```bash
cd orchestrator && ./venv/bin/python manage.py run_pool_master_data_sync_cutover --strict --gate-report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-readiness-gate-report.json --report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-cutover-rollback-snapshot-report.json
```

3. Roll back artifact to previous stable release.
4. Re-run readiness gates:

```bash
cd orchestrator && ./venv/bin/python manage.py run_pool_master_data_sync_readiness_gates --strict --signoff-platform "platform-oncall" --signoff-security "security-oncall" --signoff-operations "operations-oncall"
```

5. If gates pass and incident resolved, plan next cutover window.
