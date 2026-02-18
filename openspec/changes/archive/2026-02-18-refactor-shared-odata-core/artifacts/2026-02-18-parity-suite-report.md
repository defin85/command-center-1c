# Parity suite report: old/new transport behavior

Дата: 2026-02-18
Задача: `command-center-1c-bqza.23`

## 1) Scope parity check

Проверяли отсутствие критичных расхождений по:
- status semantics (`published/partial_success/failed`, fail-closed bridge behavior)
- diagnostics/read-model compatibility (`publication_attempts`, `publication_summary`, `diagnostics`)
- idempotency / retry semantics (`step_attempt`, transport resend attempts)
- generic CRUD stability после включения migration route

## 2) Executed suites and outcomes

### Go transport-core and drivers
Команда:
```bash
cd go-services/worker && go test ./internal/odata ./internal/drivers/poolops ./internal/drivers/workflowops ./internal/workflow/handlers ./internal/processor
```
Результат: `PASS`

### Go integration migration-path (CRUD under publication-core flags)
Команда:
```bash
cd go-services/worker && go test -tags=integration ./internal/processor -run 'TestProcessor_Integration_(CreateOperation|UpdateOperation|DeleteOperation|QueryOperation|CreateOperation_WithPoolPublicationCoreEnabled)$'
```
Результат: `PASS`

### Orchestrator contract/projection parity checks
Команда:
```bash
./.venv/bin/pytest -q orchestrator/apps/api_internal/tests/test_views_workflows.py orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py
```
Результат: `29 passed`

## 3) Coverage matrix (parity-critical)

- Publication flow via worker transport + retries: `PASS`
- Compatibility profile enforcement: `PASS`
- Bridge fail-closed contract (`409 + POOL_RUNTIME_PUBLICATION_PATH_DISABLED`): `PASS`
- Facade/read-model diagnostics compatibility: `PASS`
- Generic CRUD regression under migration flags: `PASS`

## 4) Verdict

Критичных расхождений old/new transport parity не обнаружено.
Статус задачи: **go/no-go criterion for parity suite = GO**.
