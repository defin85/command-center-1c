# Staging rehearsal + rollback drill (dry-run report)

Дата: 2026-02-18
Задача: `command-center-1c-bqza.24`

## 1) Rehearsal scope

Dry-run покрывает pre-cutover quality gates и rollback checks:
- compatibility preflight (`odata-compatibility-profile`);
- parity/integration suites для worker + orchestrator;
- fail-closed/rollback guardrails на pool publication route.

## 2) Executed dry-run checks (local)

1. Compatibility preflight:
```bash
./.venv/bin/python orchestrator/manage.py preflight_odata_compatibility_profile --configuration-id 1c-accounting-3.0-standard-odata --compatibility-mode 8.3.23 --release-profile-version 0.4.2-draft --json
```
Результат: `decision=go`, `failed_checks=0`.

2. Worker transport/drivers suite:
```bash
cd go-services/worker && go test ./internal/odata ./internal/drivers/poolops ./internal/drivers/workflowops ./internal/workflow/handlers ./internal/processor
```
Результат: `PASS`.

3. Integration migration-path subset:
```bash
cd go-services/worker && go test -tags=integration ./internal/processor -run 'TestProcessor_Integration_(CreateOperation|UpdateOperation|DeleteOperation|QueryOperation|CreateOperation_WithPoolPublicationCoreEnabled)$'
```
Результат: `PASS`.

4. Orchestrator bridge/report contract checks:
```bash
./.venv/bin/pytest -q orchestrator/apps/api_internal/tests/test_views_workflows.py orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py
```
Результат: `29 passed`.

5. Rollback guardrails (route disable / no bridge fallback):
```bash
cd go-services/worker && go test ./internal/drivers/poolops -run 'TestAdapter_ExecutePublicationOperation(RouteDisabledFailsClosed|DoesNotFallbackToBridgeWhenTransportMissing)|TestAdapter_ExecutePoolOperationRouteDecisionLatchedPerExecution'
```
Результат: `PASS`.

## 3) Staging execution status

Статус: требуется отдельный запуск в staging окружении (production-like data).

Команды/шаги для staging берутся из:
- `openspec/changes/refactor-shared-odata-core/artifacts/2026-02-18-staging-rehearsal-plan.md`
- `openspec/changes/refactor-shared-odata-core/artifacts/2026-02-18-rollback-runbook.md`
- `openspec/changes/refactor-shared-odata-core/artifacts/2026-02-18-sre-cutover-package.md`

## 4) Interim verdict

Dry-run gates: **green** (локально).
Blocking note: финальный staging rehearsal sign-off остаётся обязательным pre-cutover шагом.
