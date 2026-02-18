# Post-cutover smoke and soak report (pre-release simulation)

Дата: 2026-02-18
Связанная задача: `command-center-1c-bqza.27`

## Scope

Подтверждена готовность post-cutover smoke/soak checks на уровне pre-release симуляции:
- fail-closed bridge contract для `pool.publication_odata`;
- pool publication projection/idempotency checks;
- regression stability для worker `odata-core` и Orchestrator API.

## Executed checks

1. API-internal regression suite:
```bash
./.venv/bin/pytest -q \
  orchestrator/apps/api_internal/tests/test_views_workflows.py \
  orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py
```
Результат: `30 passed`.

2. Focused publication fail-closed and idempotency smoke:
```bash
./.venv/bin/pytest -q orchestrator/apps/api_internal/tests/test_views_workflows.py \
  -k 'publication_odata_is_fail_closed_after_cutover or run_500_on_3_targets or replays_idempotent_request_without_reapplying_side_effect'
```
Результат: `3 passed`.

3. Pool domain runtime fail-closed checks:
```bash
./.venv/bin/pytest -q orchestrator/apps/intercompany_pools/tests/test_pool_domain_steps.py
```
Результат: `4 passed`.

4. Worker transport/runtime regression slice:
```bash
cd go-services/worker && go test ./internal/odata ./internal/drivers/poolops ./internal/drivers/workflowops ./internal/workflow/handlers ./internal/processor
```
Результат: `ok` для всех пакетов.

## Soak note

В локальном/CI контуре выполнена только pre-release soak симуляция (тестовая и контрактная стабильность).
Live soak по telemetry (`latency/retries/errors/resend`) должен выполняться в согласованном release window по чеклисту:
`openspec/changes/refactor-shared-odata-core/artifacts/2026-02-18-cutover-checklist.md`.

## Status

Pre-release smoke/soak readiness: **PASS**.
Операционный live-soak в staging/prod: **awaiting release window execution**.
