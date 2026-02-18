# Big-bang cutover local execution report

Дата: 2026-02-18
Связанная задача: `command-center-1c-bqza.26`

## Scope

Локально выполнено атомарное переключение обоих путей на worker `odata-core` в едином окне:
- `odataops` route: enabled;
- `pool.publication_odata` route: enabled;
- bridge publication path: fail-closed (`409 + POOL_RUNTIME_PUBLICATION_PATH_DISABLED`).

## Runtime cutover actions

1. Обновлены worker feature flags в `.env.local`:
- `ENABLE_POOLOPS_ROUTE=true`
- `POOLOPS_ROUTE_ROLLOUT_PERCENT=1.0`
- `POOLOPS_ROUTE_KILL_SWITCH=false`
- `ENABLE_POOL_PUBLICATION_ODATA_CORE=true`
- `POOL_PUBLICATION_ODATA_CORE_ROLLOUT_PERCENT=1.0`
- `POOL_PUBLICATION_ODATA_CORE_KILL_SWITCH=false`
- compatibility gate vars (`ODATA_COMPATIBILITY_*`) для publication path.

2. Worker бинарник пересобран из актуального коммита:
```bash
bash ./scripts/build.sh --service=worker
```
- version/commit: `354ffdae`.

3. Подняты два worker процесса с раздельными stream/group:
- operations worker: `commands:worker:operations`, metrics `:9191`;
- workflows worker: `commands:worker:workflows`, metrics `:9092`.

## Evidence

1. Worker endpoints healthy:
```bash
curl http://localhost:9191/health
curl http://localhost:9092/health
```
- оба вернули `{"status":"healthy"...}`.

2. Worker process env подтверждает atomic route enablement:
- `ENABLE_POOLOPS_ROUTE=true`
- `ENABLE_POOL_PUBLICATION_ODATA_CORE=true`
- `POOL_PUBLICATION_ODATA_CORE_ROLLOUT_PERCENT=1.0`
- `ODATA_COMPATIBILITY_WRITE_CONTENT_TYPE=application/json;odata=nometadata`

3. Bridge fail-closed smoke на live local runtime:
```bash
POST /api/v2/internal/workflows/execute-pool-runtime-step
operation_type=pool.publication_odata
```
- HTTP `409`
- response: `{ "code": "POOL_RUNTIME_PUBLICATION_PATH_DISABLED", ... }`

4. UI smoke через `agent-browser`:
- успешный вход (`admin / p-123456`);
- открыта страница Runtime Settings;
- screenshot: `logs/cutover26-runtime-settings.png`.

## Status

`7.1` local cutover: **PASS**.

Ограничение:
- отчет относится к локальному execution window;
- production/staging release window требует отдельного operator runbook execution.
