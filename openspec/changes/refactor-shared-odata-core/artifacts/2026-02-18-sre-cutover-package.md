# SRE cutover package: thresholds, abort criteria, smoke checks

Дата: 2026-02-18
Задача: `command-center-1c-bqza.19`

## 1) Alert thresholds (post-cutover monitoring)

Окно наблюдения: rolling `5m`, подтверждение алерта при удержании `>=10m`.

1. Transport error rate (non-retryable):
- Метрика: `rate(cc1c_odata_transport_errors_total{retryable="false"}[5m])`
- Threshold:
  - warning: `> 0.05 rps` по любому `operation`
  - critical: `> 0.2 rps` по любому `operation`

2. Retry pressure:
- Метрика: `rate(cc1c_odata_transport_retries_total[5m])`
- Threshold:
  - warning: рост > 2x относительно pre-cutover baseline
  - critical: рост > 4x относительно pre-cutover baseline

3. P95 transport latency:
- Метрика: `histogram_quantile(0.95, sum by (le, operation) (rate(cc1c_odata_transport_latency_seconds_bucket[5m])))`
- Threshold:
  - warning: `> 2.0s`
  - critical: `> 5.0s`

4. Resend attempt anomaly:
- Метрика: `rate(cc1c_odata_transport_resend_attempt_total[5m])`
- Threshold:
  - warning: рост > 2x baseline
  - critical: рост > 3x baseline + одновременный рост `errors_total`

## 2) Abort criteria (go/no-go during cutover)

Abort cutover и запуск rollback обязателен, если выполняется хотя бы одно:
- critical alert по non-retryable errors держится `>=10m`;
- critical alert по latency держится `>=10m`;
- bridge/facade контракт нарушен (`pool.publication_odata` bridge не возвращает `409 + POOL_RUNTIME_PUBLICATION_PATH_DISABLED`);
- фиксируется несовместимость `PoolRunReport` diagnostics payload (breaking client contract);
- на post-cutover smoke есть блокирующий fail в CRUD или publication flow.

## 3) Post-cutover smoke checklist

1. Bridge fail-closed:
- `POST /api/v2/internal/workflows/execute-pool-runtime-step` с `operation_type=pool.publication_odata`
- Ожидание: `409`, `code=POOL_RUNTIME_PUBLICATION_PATH_DISABLED`

2. Generic CRUD (worker odataops):
- smoke create/update/delete/query на тестовой ИБ
- Ожидание: операции успешны, без аномального retry/error роста

3. Publication flow:
- запустить тестовый pool run с минимум 2 target DB
- Ожидание: корректный terminal status (`published|partial_success|failed`) + валидные attempts/diagnostics

4. Facade compatibility:
- `GET /api/v2/pools/runs/{run_id}/report`
- Ожидание: совместимый payload (`publication_attempts`, `publication_summary`, `diagnostics`)

5. Telemetry sanity:
- сравнить `operation=odataops.*` и `operation=pool.publication_odata` по latency/retry/error/resend
- убедиться в отсутствии critical threshold breach

## 4) Ownership

- Worker (Go): transport metrics/tracing, retry/error behavior.
- Orchestrator API (Python): bridge fail-closed contract and facade compatibility.
- Platform/SRE: alert rules, cutover watch, abort/rollback decision.
