## POOL_MASTER_DATA_SYNC Big-Bang Cutover Runbook

Цель: безопасно выполнить cutover unified sync runtime для in-flight нагрузки по протоколу `freeze -> drain -> watermark capture -> enable` и иметь детерминированный rollback с revalidation gates.

### Обязательные preconditions

1. Readiness gate report `overall_status=pass`:
- `docs/observability/artifacts/refactor-08/pool-master-data-sync-readiness-gate-report.json`

2. ORR sign-off заполнен по ролям:
- `platform`
- `security`
- `operations`

3. Release window и канал инцидента подтверждены.

### Cutover (single-shot, non-prod)

#### 1) Dry-run (обязателен перед apply)

```bash
cd orchestrator && ./venv/bin/python manage.py run_pool_master_data_sync_cutover --strict --gate-report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-readiness-gate-report.json --report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-cutover-dry-run-report.json
```

Проверить в отчёте:
- `stages.freeze.applied=false`
- `stages.drain.drained=true`
- `stages.watermark_capture.*` заполнены
- `stages.gate_report.overall_status=pass`

#### 2) Apply (enable)

```bash
cd orchestrator && ./venv/bin/python manage.py run_pool_master_data_sync_cutover --execute-enable --strict --gate-report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-readiness-gate-report.json --report-path docs/observability/artifacts/refactor-08/pool-master-data-sync-cutover-apply-report.json
```

Проверить:
- `execution_mode=apply`
- `stages.freeze.applied=true`
- `stages.drain.drained=true`
- `stages.enable.enabled_value_after=true`
- `overall_status=pass`

### Rollback protocol (in-flight safe)

#### Trigger criteria

- любой gate-breaking инцидент после enable;
- регресс commit-before-ack/checkpoint;
- security leak в diagnostics/last_error.

#### Steps

1. Freeze runtime (запретить новое исполнение):

```bash
cd orchestrator && ./venv/bin/python manage.py shell -c "from apps.runtime_settings.models import RuntimeSetting; RuntimeSetting.objects.update_or_create(key='pools.master_data.sync.enabled', defaults={'value': False}); print('sync.enabled=false')"
```

2. Capture rollback watermark:
- повторно запустить dry-run команду и сохранить fresh отчёт;
- зафиксировать `stages.watermark_capture`.

3. Artifact rollback:
- откатить релизный артефакт до последнего стабильного.

4. Replay-safe recovery:
- убедиться, что `stages.drain.drained=true`;
- выполнить revalidation gates (`run_pool_master_data_sync_readiness_gates --strict ...`).

5. Decision:
- если gates pass: планировать повторный enable;
- если fail: остаёмся в freeze, запускаем RCA/remediation.

### Пост-cutover контроль

1. Проверить runtime setting:

```bash
cd orchestrator && ./venv/bin/python manage.py shell -c "from apps.runtime_settings.models import RuntimeSetting; s=RuntimeSetting.objects.filter(key='pools.master_data.sync.enabled').first(); print(s.value if s else None)"
```

2. Проверить gate + cutover отчёты в `docs/observability/artifacts/refactor-08/`.
3. Обновить post-cutover readiness report для следующего окружения.
