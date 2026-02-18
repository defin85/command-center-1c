# Big-bang cutover execution readiness

Дата: 2026-02-18
Связанная задача: `command-center-1c-bqza.26`

## 1) What is already ready (pre-cutover)

- `odataops` и `pool.publication_odata` переведены на worker `odata-core` (код + тесты).
- Bridge publication path fail-closed (`409 + POOL_RUNTIME_PUBLICATION_PATH_DISABLED`) зафиксирован и покрыт контрактными тестами.
- Parity suite и migration-path integration tests зелёные.
- Compatibility preflight проходит (`decision=go`).
- SRE cutover package, dashboard checks, rollback runbook и rehearsal artifacts подготовлены.

Артефакты:
- `2026-02-18-parity-suite-report.md`
- `2026-02-18-sre-cutover-package.md`
- `2026-02-18-staging-rehearsal-dry-run-report.md`
- `2026-02-18-e2e-regression-run500-report.md`

## 2) Blocking step for task .26

Полное выполнение `7.1` требует **реального релизного окна** и деплоя в целевое окружение:
- одновременное включение runtime/config для двух путей;
- подтверждение факта cutover по live telemetry и runtime smoke;
- фиксация timestamped release evidence.

В локальном/CI контуре этот шаг нельзя завершить полностью без доступа к staging/prod deployment pipeline.

## 3) Operator run commands (for release window)

1. Pre-check:
```bash
openspec validate refactor-shared-odata-core --strict --no-interactive
```

2. Compatibility gate:
```bash
./.venv/bin/python orchestrator/manage.py preflight_odata_compatibility_profile \
  --configuration-id 1c-accounting-3.0-standard-odata \
  --compatibility-mode 8.3.23 \
  --release-profile-version 0.4.2-draft \
  --json
```

3. Worker/Orchestrator regression slices:
```bash
cd go-services/worker && go test ./internal/odata ./internal/drivers/poolops ./internal/drivers/workflowops ./internal/workflow/handlers ./internal/processor
./.venv/bin/pytest -q orchestrator/apps/api_internal/tests/test_views_workflows.py orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py
```

4. Release window smoke (post-deploy):
- bridge publication call returns `409 + POOL_RUNTIME_PUBLICATION_PATH_DISABLED`;
- facade details/report compatible for new runs;
- CRUD smoke on odataops is green.

## 4) Status

`Task .26` readiness: **Prepared, awaiting real release window execution**.
