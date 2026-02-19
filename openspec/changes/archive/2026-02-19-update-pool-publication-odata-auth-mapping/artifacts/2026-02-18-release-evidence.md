# Release evidence (local dry-run): update-pool-publication-odata-auth-mapping

Дата: 2026-02-18

## 1. Локальные quality gates
- `openspec validate update-pool-publication-odata-auth-mapping --strict --no-interactive` -> PASS.
- Go:
  - `go test ./internal/drivers/poolops` -> PASS.
- Python:
  - `apps/intercompany_pools/tests/test_workflow_runtime.py` -> PASS.
  - `apps/intercompany_pools/tests/test_publication_auth_preflight_command.py` -> PASS.
  - `apps/operations/tests/test_event_subscriber_commands.py` -> PASS.
  - `apps/api_v2/tests/test_intercompany_pool_runs.py` -> PASS.
- Frontend:
  - `vitest run src/pages/Pools/__tests__/PoolRunsPage.test.tsx` -> PASS.

## 2. Проверенные сценарии
- Fail-fast preflight при запуске run:
  - missing actor mapping -> `ODATA_MAPPING_NOT_CONFIGURED` + remediation route `/rbac`.
  - ambiguous service mapping -> `ODATA_MAPPING_AMBIGUOUS`.
- Success path:
  - actor mapping success (API create run + workflow runtime).
  - service mapping success (workflow runtime с `requested_by=None`).
- Worker publication transport:
  - context-aware credentials lookup (`created_by`, `ib_auth_strategy`, `credentials_purpose`).
  - telemetry outcome labels (`actor_success`, `service_success`, `missing_mapping`, `ambiguous_mapping`, `invalid_auth_context`).

## 3. Статус операторского sign-off
- `staging` operator sign-off: PENDING (требуется выполнение в staging окружении).
- `production` operator sign-off: PENDING (выполняется только после staging `GO`).

## 4. Решение по локальной готовности
- Локальный dry-run verdict: **READY FOR STAGING**.
- Финальный production go/no-go зависит от mandatory operator sign-off в реальном релизном окне.

