## API SLO (Production Readiness)

Цель: иметь измеримый контроль над качеством API (успешность и латентность) и автоматические стоп-сигналы (alerts + go/no-go checks) перед выкатыванием изменений.

### Источники метрик

- **API Gateway**: `cc1c_requests_total{method,path,status}` и `cc1c_request_duration_seconds_bucket{method,path,le}`.
- **Orchestrator (Django)**: `django_prometheus` (`/metrics`), используется для внутренней диагностики; SLO для “user-perceived” измеряется по Gateway.

### SLI определения

- **Availability (server-side)**: доля запросов, **не** завершившихся `5xx`.
  - `availability = 1 - (rate(5xx) / rate(all))`
- **Latency**: `p95` и `p99` по `cc1c_request_duration_seconds_bucket`.

Важно: `4xx` считаются “клиентской ошибкой” и не входят в server-side availability, но мониторятся отдельно (как сигнал UX/RBAC/валидации).

### SLO цели (по умолчанию)

Глобально для API Gateway (по `/api/v2/*` суммарно):
- **Availability (non-5xx)**: ≥ **99%** (rolling 30m)
- **Latency p95**: < **0.5s** (rolling 30m)
- **Latency p99**: < **2.0s** (rolling 30m)

Для “критичных” admin actions (по отдельным путям):
- `/api/v2/operations/execute/`
- `/api/v2/extensions/batch-install/`
- `/api/v2/clusters/sync-cluster/`
- `/api/v2/workflows/execute-workflow/`

Цели:
- **Availability (non-5xx)**: ≥ **99%** (rolling 30m)
- **Latency p95**: < **1.0s** (rolling 30m)
- **Latency p99**: < **5.0s** (rolling 30m)

### Где смотреть

- Grafana: dashboard **“API SLO”** (см. `infrastructure/monitoring/grafana/dashboards/api-slo.json`)
- Prometheus: `infrastructure/monitoring/prometheus/recording_rules.yml` и alerts в `infrastructure/monitoring/prometheus/alerts/api_slo_alerts.yml`

### Go/No-Go (локально / перед релизом)

Скрипт читает Prometheus и валидирует SLO пороги:

```bash
./scripts/rollout/check-api-slo.sh --lookback=30m
```

