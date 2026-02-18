# Post-cutover smoke/soak local execution report

Дата: 2026-02-18  
Связанная задача: `command-center-1c-bqza.27`

## Scope

В локальном post-cutover окне подтверждены:
- fail-closed поведение bridge path для `pool.publication_odata`;
- совместимость facade report payload (`/api/v2/pools/runs/{run_id}/report/`);
- базовая telemetry-стабильность в short soak window (6 probe итераций, шаг 10с).

Контекст окна:
- cutover состояния из `2026-02-18-bigbang-cutover-local-window-report.md` активны;
- worker processes (`operations`, `workflows`) запущены и healthy;
- orchestrator `/health` = `ok`.

## Executed smoke checks

1) Bridge fail-closed (single call)
- Endpoint: `POST /api/v2/internal/workflows/execute-pool-runtime-step`
- Result: `HTTP 409`, `code=POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.

2) Bridge fail-closed + facade compatibility (soak probes)
- Выполнено 6 итераций подряд:
  - bridge call: ожидаемо `HTTP 409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`;
  - report call: `GET /api/v2/pools/runs/{run_id}/report/` с JWT + `X-CC1C-Tenant-ID`;
  - report invariant: `run.status=validated`, `publication_attempts=[]`.
- Result: все 6/6 probe итераций PASS.

## Telemetry soak snapshot

Baseline -> Final (delta):
- `cc1c_orchestrator_requests_total{method="POST",status="409"}`: `2 -> 8` (`+6`, ожидаемо из bridge fail-closed probes).
- `cc1c_orchestrator_requests_total{method="POST",status="500"}`: `0 -> 0` (`+0`).
- `cc1c_orchestrator_api_v2_errors_total`: `0 -> 0` (`+0`).
- `worker_ops external_http_requests_total{status="error"}`: `25 -> 28` (`+3`).
- `worker_workflows external_http_requests_total{status="error"}`: `0 -> 0` (`+0`).

Примечание по `worker_ops +3`:
- рост зафиксирован в metadata health-check path (`/conf_test/.../$metadata`, `/test_lock_unlock/.../$metadata`, `/odata/standard.odata/$metadata`);
- это фоновые ошибки health-check окружения и не связано с bridge publication path;
- bridge path в окне оставался fail-closed, side effects не применялись (`publication_attempts` стабильно `0`).

## Status

`7.2` local post-cutover smoke/soak: **PASS (local window)**.

Ограничение:
- staging/prod live soak и operator sign-off остаются обязательными отдельными шагами release window.
