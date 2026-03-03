## POOL_MASTER_DATA_SYNC Readiness Gates

Документ фиксирует формальные пороги Go/No-Go для big-bang enablement unified sync runtime и обязательный ORR sign-off.

### Формальные пороги (pass/fail)

`load`
- `reconcile_window_p95_seconds <= 120`
- `reconcile_window_p99_seconds <= 150`
- `coverage_ratio >= 0.995`
- `partial_outcome_rate <= 0.05`

`replay_consistency`
- `lost_events_total == 0`
- `duplicate_apply_total == 0`
- `deterministic_replay_match_ratio == 1.0`

`failover_restart`
- `checkpoint_monotonicity_violations == 0`
- `ack_before_commit_violations == 0`
- `worker_recovery_to_steady_state_seconds <= 60`

`security`
- `secrets_exposed_in_diagnostics == 0`
- `secrets_exposed_in_last_error == 0`
- `redaction_test_failures == 0`

### Machine-readable schema

- Schema file:
  - `docs/observability/schemas/pool_master_data_sync_readiness_gate_report.schema.json`
- `schema_version`:
  - `pool_master_data_sync_readiness_gate_report.v1`

Отчёт содержит:
- top-level: `schema_version`, `generated_at_utc`, `overall_status`
- gate sections: `load`, `replay_consistency`, `failover_restart`, `security`
- по каждой секции: `status`, `measured_values`, `thresholds`, `checks`, `evidence_refs`
- ORR блок: `required_roles`, `signed_off_by`, `missing_roles`, `status`

### ORR sign-off checklist (обязательный)

1. `platform`
- подтверждена стабильность runtime и мониторинга;
- подтверждён rollback-путь и сохранность watermark/checkpoint.

2. `security`
- подтверждён zero-leak по diagnostics/last_error;
- подтверждена redaction-политика для секретов.

3. `operations`
- подтверждена операционная готовность runbook/triage;
- подтверждена воспроизводимость gate-report в non-prod.

Правило:
- enablement блокируется, если отсутствует sign-off хотя бы одной роли.

### Gate-runner (blocking pre-cutover)

Команда:

```bash
cd orchestrator && ./venv/bin/python manage.py run_pool_master_data_sync_readiness_gates --strict --signoff-platform "platform-oncall" --signoff-security "security-oncall" --signoff-operations "operations-oncall"
```

По умолчанию команда:
- строит load-model для `6x120` (`720` scope/window);
- запускает pytest-gates для replay/failover/security;
- сохраняет отчёт:
  - `docs/observability/artifacts/refactor-08/pool-master-data-sync-readiness-gate-report.json`

Если `overall_status != pass`, команда в `--strict` завершится с non-zero exit code.
