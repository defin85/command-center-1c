# OpenSpec validate and release evidence

Дата: 2026-02-18
Связанная задача: `command-center-1c-bqza.29`

## 1) OpenSpec strict validation

Команда:
```bash
openspec validate refactor-shared-odata-core --strict --no-interactive
```

Результат:
- `Change 'refactor-shared-odata-core' is valid`

## 2) Compatibility preflight gate

Команда:
```bash
./.venv/bin/python orchestrator/manage.py preflight_odata_compatibility_profile \
  --configuration-id 1c-accounting-3.0-standard-odata \
  --compatibility-mode 8.3.23 \
  --release-profile-version 0.4.2-draft \
  --json
```

Результат:
- `decision=go`
- checks passed: `6/6`
- profile: `0.4.2-draft`, configuration: `1c-accounting-3.0-standard-odata`

## 3) Regression evidence snapshot

```bash
./.venv/bin/pytest -q \
  orchestrator/apps/api_internal/tests/test_views_workflows.py \
  orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py
```
Результат: `30 passed`.

```bash
cd go-services/worker && go test ./internal/odata ./internal/drivers/poolops ./internal/drivers/workflowops ./internal/workflow/handlers ./internal/processor
```
Результат: `ok` для всех целевых пакетов.

## 4) Linked artifacts

- `2026-02-18-parity-suite-report.md`
- `2026-02-18-staging-rehearsal-dry-run-report.md`
- `2026-02-18-e2e-regression-run500-report.md`
- `2026-02-18-post-cutover-smoke-soak-report.md`
- `2026-02-18-legacy-transport-cleanup-report.md`

## Status

Strict validation and release evidence package: **PASS**.
